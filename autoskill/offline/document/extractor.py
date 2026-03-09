"""
Evidence extraction stage for the offline document pipeline.

This stage converts normalized `DocumentRecord` objects into atomic
`EvidenceUnit` objects. The extractor interface is intentionally pluggable so
future LLM-backed implementations can be added without changing the pipeline
or CLI layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import uuid
from typing import Dict, List, Protocol

from .common import StageLogger, emit_stage_log, normalize_text
from .models import DocumentRecord, EvidenceUnit, ProvenanceRecord, TextSpan

_TASK_KEYWORDS = [
    ("classification", ["classify", "classification", "categorize", "taxonomy", "分类"]),
    ("extraction", ["extract", "extraction", "parse", "pull", "提取", "抽取", "解析"]),
    ("analysis", ["analyze", "analysis", "assess", "review", "评估", "分析", "审查"]),
    ("planning", ["plan", "planning", "strategy", "design", "规划", "设计", "策略"]),
    ("generation", ["generate", "generation", "compose", "write", "draft", "生成", "撰写"]),
    ("validation", ["validate", "validation", "verify", "test", "check", "验证", "校验", "检查"]),
    ("monitoring", ["monitor", "monitoring", "observe", "track", "监控", "跟踪"]),
    ("transformation", ["transform", "convert", "rewrite", "normalize", "转换", "改写", "规范化"]),
    ("decision", ["decide", "decision", "rule", "branch", "决策", "判断"]),
]

_METHOD_KEYWORDS = [
    ("workflow", ["workflow", "procedure", "protocol", "pipeline", "流程", "步骤", "方法"]),
    ("checklist", ["checklist", "criteria", "rubric", "清单", "标准"]),
    ("template", ["template", "schema", "format", "contract", "模板", "格式"]),
    ("heuristic", ["heuristic", "rule-based", "启发式", "规则"]),
    ("comparison", ["compare", "comparison", "benchmark", "对比", "比较"]),
    ("scoring", ["score", "scoring", "ranking", "打分", "评分"]),
    ("observation", ["observe", "observation", "field notes", "观察"]),
    ("review", ["review", "inspection", "audit", "审阅", "审计"]),
]

_STAGE_KEYWORDS = [
    ("intake", ["background", "input", "context", "overview", "summary", "背景", "输入", "概述"]),
    ("analysis", ["analysis", "assess", "evaluate", "review", "analy", "分析", "评估", "审查"]),
    ("planning", ["plan", "design", "strategy", "规划", "设计", "策略"]),
    ("execution", ["method", "procedure", "workflow", "apply", "execute", "实施", "执行", "方法"]),
    ("validation", ["validate", "check", "monitor", "verify", "test", "验证", "检查", "监控"]),
    ("reporting", ["output", "report", "result", "summary", "结论", "输出", "结果"]),
]

_CONSTRAINT_PATTERNS = ["must", "should", "need to", "do not", "avoid", "禁止", "必须", "应当", "不要", "不得"]
_DECISION_PATTERNS = ["if ", "when ", "unless", "otherwise", "如果", "当", "否则"]
_FAILURE_PATTERNS = ["fail", "failure", "error", "risk", "warning", "注意", "失败", "错误", "风险"]
_OUTPUT_PATTERNS = ["output", "return", "report", "deliver", "输出", "结果", "返回", "交付"]
_TRIGGER_PATTERNS = ["trigger", "when asked", "use when", "适用", "触发", "在.*时"]
_WORKFLOW_PATTERNS = [r"^\s*[\-\*\u2022]\s+", r"^\s*\d+[\.\)]\s+"]
_NEGATION_PATTERNS = ["not ", "never", "avoid", "禁止", "不要", "不得", "无须"]
def _contains_any(text: str, patterns: List[str]) -> bool:
    """Returns True when a text contains any keyword pattern."""

    low = str(text or "").lower()
    for pattern in patterns:
        try:
            if re.search(pattern, low):
                return True
        except re.error:
            if pattern.lower() in low:
                return True
    return False


def _infer_family(text: str, mapping: List[tuple[str, List[str]]], *, fallback: str = "general") -> str:
    """Infers task/method/stage families from generic keyword maps."""

    low = str(text or "").lower()
    for label, patterns in mapping:
        for pattern in patterns:
            if pattern.lower() in low:
                return label
    return fallback


def _detect_claim_type(text: str) -> str:
    """Assigns a coarse evidence type using generic structural signals."""

    src = str(text or "")
    low = src.lower()
    if any(re.search(pattern, src) for pattern in _WORKFLOW_PATTERNS):
        return "workflow_step"
    if _contains_any(low, _FAILURE_PATTERNS):
        return "failure_mode"
    if _contains_any(low, _OUTPUT_PATTERNS):
        return "output_contract"
    if _contains_any(low, _DECISION_PATTERNS):
        return "decision_rule"
    if _contains_any(low, _CONSTRAINT_PATTERNS):
        return "constraint"
    if _contains_any(low, _TRIGGER_PATTERNS):
        return "trigger_condition"
    return "observation"


def _claim_confidence(text: str, claim_type: str) -> float:
    """Assigns a lightweight confidence score to heuristic evidence units."""

    score = 0.55
    if claim_type in {"workflow_step", "decision_rule", "constraint"}:
        score += 0.15
    if _contains_any(text, _WORKFLOW_PATTERNS):
        score += 0.1
    if len(normalize_text(text)) > 40:
        score += 0.05
    if _contains_any(text, _FAILURE_PATTERNS + _OUTPUT_PATTERNS + _DECISION_PATTERNS):
        score += 0.05
    return min(score, 0.95)


def _split_section_blocks(text: str) -> List[str]:
    """Splits section text into paragraph-like evidence blocks."""

    src = str(text or "").strip()
    if not src:
        return []
    blocks: List[str] = []
    for paragraph in [p.strip() for p in src.split("\n\n") if p.strip()]:
        lines = [ln.strip() for ln in paragraph.splitlines() if ln.strip()]
        bullet_lines = [
            ln
            for ln in lines
            if any(re.search(pattern, ln) for pattern in _WORKFLOW_PATTERNS)
        ]
        if bullet_lines and len(bullet_lines) == len(lines):
            blocks.extend(bullet_lines)
            continue
        blocks.append(paragraph)
    return blocks


def _block_span(record: DocumentRecord, *, section_start: int, block: str, cursor: int) -> TextSpan:
    """Builds a best-effort source span for one extracted evidence block."""

    raw = str(record.raw_text or "")
    target = str(block or "").strip()
    if not target:
        return TextSpan(start=section_start, end=section_start)
    idx = raw.find(target, max(0, int(cursor)))
    if idx < 0:
        idx = raw.find(target, max(0, int(section_start)))
    if idx < 0:
        idx = max(0, int(section_start))
    return TextSpan(start=idx, end=idx + len(target))


@dataclass
class EvidenceExtractionResult:
    """Output of the evidence extraction stage."""

    documents: List[DocumentRecord] = field(default_factory=list)
    evidence_units: List[EvidenceUnit] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)
    extractor_name: str = "heuristic"


class EvidenceExtractor(Protocol):
    """Pluggable evidence extractor interface."""

    def extract(
        self,
        *,
        documents: List[DocumentRecord],
        logger: StageLogger,
    ) -> EvidenceExtractionResult:
        """Extracts evidence units from normalized document records."""


class HeuristicEvidenceExtractor:
    """Rule-based evidence extractor used by the MVP pipeline."""

    def extract(
        self,
        *,
        documents: List[DocumentRecord],
        logger: StageLogger,
    ) -> EvidenceExtractionResult:
        """Extracts atomic evidence units using generic textual heuristics."""

        result = EvidenceExtractionResult(documents=list(documents or []), extractor_name="heuristic")
        for record in documents or []:
            try:
                units = self._extract_from_document(record)
                result.evidence_units.extend(units)
                emit_stage_log(logger, f"[extract_evidence] doc={record.doc_id} evidence={len(units)}")
            except Exception as e:
                result.errors.append({"doc_id": record.doc_id, "error": str(e)})
                emit_stage_log(logger, f"[extract_evidence] error doc={record.doc_id}: {e}")
        return result

    def _extract_from_document(self, record: DocumentRecord) -> List[EvidenceUnit]:
        """Extracts evidence units from one document record."""

        out: List[EvidenceUnit] = []
        sections = list(record.sections or [])
        if not sections and str(record.raw_text or "").strip():
            sections = []
        for section in sections or []:
            cursor = int(section.span.start or 0)
            section_text = str(section.text or "").strip()
            if not section_text:
                continue
            for block in _split_section_blocks(section_text):
                normalized = normalize_text(block)
                if len(normalized) < 12:
                    continue
                signal_text = f"{section.heading}\n{normalized}".strip()
                claim_type = _detect_claim_type(signal_text)
                method_family = _infer_family(signal_text, _METHOD_KEYWORDS)
                task_family = _infer_family(signal_text, _TASK_KEYWORDS)
                span = _block_span(record, section_start=section.span.start, block=block, cursor=cursor)
                cursor = int(span.end or cursor)
                evidence_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"autoskill-evidence:{record.doc_id}:{section.heading}:{claim_type}:{normalized}",
                    )
                )
                out.append(
                    EvidenceUnit(
                        evidence_id=evidence_id,
                        doc_id=record.doc_id,
                        claim_type=claim_type,
                        section=section.heading,
                        span=span,
                        normalized_claim=normalized,
                        verbatim_excerpt=str(block or "").strip(),
                        method_family=method_family,
                        task_family=task_family,
                        confidence=_claim_confidence(signal_text, claim_type),
                        provenance=ProvenanceRecord(
                            source_type=record.source_type,
                            source_file=str((record.metadata or {}).get("source_file") or ""),
                            section=section.heading,
                            span=span,
                            metadata={
                                "document_title": record.title,
                                "domain": record.domain,
                                "section_level": section.level,
                            },
                        ),
                    )
                )
        if not out and str(record.raw_text or "").strip():
            block = normalize_text(record.raw_text)
            evidence_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"autoskill-evidence:{record.doc_id}:{block}"))
            out.append(
                EvidenceUnit(
                    evidence_id=evidence_id,
                    doc_id=record.doc_id,
                    claim_type="observation",
                    section=record.title,
                    span=TextSpan(start=0, end=len(record.raw_text)),
                    normalized_claim=block,
                    verbatim_excerpt=record.raw_text.strip(),
                    method_family=_infer_family(block, _METHOD_KEYWORDS),
                    task_family=_infer_family(block, _TASK_KEYWORDS),
                    confidence=0.5,
                    provenance=ProvenanceRecord(
                        source_type=record.source_type,
                        source_file=str((record.metadata or {}).get("source_file") or ""),
                        section=record.title,
                        span=TextSpan(start=0, end=len(record.raw_text)),
                        metadata={"document_title": record.title, "domain": record.domain},
                    ),
                )
            )
        return out


def build_evidence_extractor(kind: str = "heuristic") -> EvidenceExtractor:
    """Builds a concrete evidence extractor implementation."""

    name = str(kind or "").strip().lower() or "heuristic"
    if name in {"heuristic", "stub", "rule-based", "rule_based"}:
        return HeuristicEvidenceExtractor()
    raise ValueError(f"unsupported evidence extractor: {kind}")


def extract_evidence(
    *,
    documents: List[DocumentRecord],
    extractor: Optional[EvidenceExtractor] = None,
    logger: StageLogger = None,
) -> EvidenceExtractionResult:
    """Public functional wrapper for the evidence extraction stage."""

    impl = extractor or HeuristicEvidenceExtractor()
    return impl.extract(documents=list(documents or []), logger=logger)
