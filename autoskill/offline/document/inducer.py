"""
Capability induction stage for the offline document pipeline.

This stage groups `EvidenceUnit` objects into reusable `CapabilitySpec`
objects. The grouping logic is deliberately lightweight and replaceable so an
LLM-backed inducer can be introduced later without changing registry or CLI
behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import uuid
from typing import Dict, List, Optional, Protocol, Tuple

from .common import StageLogger, dedupe_strings, emit_stage_log, normalize_text
from .models import CapabilitySpec, DocumentRecord, EvidenceUnit

_STAGE_KEYWORDS = [
    ("intake", ["background", "input", "context", "overview", "summary", "背景", "输入", "概述"]),
    ("analysis", ["analysis", "assess", "evaluate", "review", "分析", "评估", "审查"]),
    ("planning", ["plan", "design", "strategy", "规划", "设计", "策略"]),
    ("execution", ["workflow", "method", "procedure", "apply", "execute", "流程", "执行", "方法"]),
    ("validation", ["validate", "verify", "check", "monitor", "验证", "校验", "检查", "监控"]),
    ("reporting", ["output", "report", "result", "summary", "输出", "结果", "结论"]),
]

_INPUT_PATTERNS = ["input", "source", "given", "context", "资料", "输入", "依据", "基于"]
_NEGATION_PATTERNS = [" not ", " never ", " avoid ", "禁止", "不要", "不得", "无须"]
def _infer_stage(text: str) -> str:
    """Infers a generic stage label from section headings and claims."""

    low = normalize_text(text, lower=True)
    for label, patterns in _STAGE_KEYWORDS:
        for pattern in patterns:
            if pattern.lower() in low:
                return label
    return "execution"


def _token_set(text: str) -> set[str]:
    """Converts a claim to a simple lexical token set."""

    return {tok for tok in re.split(r"[^\w\u4e00-\u9fff]+", normalize_text(text, lower=True)) if tok}


def _looks_conflicting(a: EvidenceUnit, b: EvidenceUnit) -> bool:
    """Detects coarse contradictions between similarly scoped evidence claims."""

    if a.doc_id != b.doc_id:
        return False
    tokens_a = _token_set(a.normalized_claim)
    tokens_b = _token_set(b.normalized_claim)
    if not tokens_a or not tokens_b:
        return False
    overlap = len(tokens_a & tokens_b) / max(1, min(len(tokens_a), len(tokens_b)))
    if overlap < 0.6:
        return False
    neg_a = any(pat in f" {normalize_text(a.normalized_claim, lower=True)} " for pat in _NEGATION_PATTERNS)
    neg_b = any(pat in f" {normalize_text(b.normalized_claim, lower=True)} " for pat in _NEGATION_PATTERNS)
    return neg_a != neg_b


def _dedupe(items: List[str]) -> List[str]:
    """Deduplicates string lists while preserving order."""

    return dedupe_strings(items, lower=True)


def _extract_inputs_from_claim(claim: str) -> Optional[str]:
    """Returns a claim text if it looks like an input requirement."""

    text = str(claim or "").strip()
    low = text.lower()
    if any(pattern in low for pattern in _INPUT_PATTERNS):
        return text
    return None


def _build_capability_title(
    *,
    document: DocumentRecord,
    task_family: str,
    method_family: str,
    stage: str,
) -> str:
    """Builds a generic capability title from grouped evidence families."""

    parts = [part for part in [task_family, method_family, stage] if str(part or "").strip() and part != "general"]
    if parts:
        return " / ".join(parts)
    return str(document.title or "document capability").strip() or "document capability"


def _capability_group_key(document: DocumentRecord, unit: EvidenceUnit) -> Tuple[str, str, str, str]:
    """Computes the grouping key used by the heuristic capability inducer."""

    stage = _infer_stage(f"{unit.section}\n{unit.normalized_claim}")
    task = str(unit.task_family or "").strip() or "general"
    method = str(unit.method_family or "").strip() or "general"
    return (document.doc_id, task, method, stage)


@dataclass
class CapabilityInductionResult:
    """Output of the capability induction stage."""

    documents: List[DocumentRecord] = field(default_factory=list)
    evidence_units: List[EvidenceUnit] = field(default_factory=list)
    capabilities: List[CapabilitySpec] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)
    inducer_name: str = "heuristic"


class CapabilityInducer(Protocol):
    """Pluggable capability inducer interface."""

    def induce(
        self,
        *,
        documents: List[DocumentRecord],
        evidence_units: List[EvidenceUnit],
        logger: StageLogger,
    ) -> CapabilityInductionResult:
        """Groups evidence units into capability specifications."""


class HeuristicCapabilityInducer:
    """Rule-based capability inducer used by the MVP pipeline."""

    def induce(
        self,
        *,
        documents: List[DocumentRecord],
        evidence_units: List[EvidenceUnit],
        logger: StageLogger,
    ) -> CapabilityInductionResult:
        """Builds capability groups from evidence families and section stages."""

        result = CapabilityInductionResult(
            documents=list(documents or []),
            evidence_units=[EvidenceUnit.from_dict(unit.to_dict()) for unit in list(evidence_units or [])],
            inducer_name="heuristic",
        )
        docs_by_id = {doc.doc_id: doc for doc in documents or []}
        self._mark_conflicts(result.evidence_units)

        grouped: Dict[Tuple[str, str, str, str], List[EvidenceUnit]] = {}
        for unit in result.evidence_units:
            doc = docs_by_id.get(unit.doc_id)
            if doc is None:
                result.errors.append({"doc_id": unit.doc_id, "error": "missing document context"})
                continue
            key = _capability_group_key(doc, unit)
            grouped.setdefault(key, []).append(unit)

        for key, units in grouped.items():
            try:
                doc_id, task_family, method_family, stage = key
                document = docs_by_id[doc_id]
                title = _build_capability_title(
                    document=document,
                    task_family=task_family,
                    method_family=method_family,
                    stage=stage,
                )
                capability_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"autoskill-capability:{document.doc_id}:{task_family}:{method_family}:{stage}:{title}",
                    )
                )
                workflow_steps = _dedupe(
                    [u.normalized_claim for u in units if u.claim_type in {"workflow_step", "observation"}]
                )
                decision_rules = _dedupe(
                    [u.normalized_claim for u in units if u.claim_type == "decision_rule"]
                )
                constraints = _dedupe(
                    [u.normalized_claim for u in units if u.claim_type == "constraint"]
                )
                failure_modes = _dedupe(
                    [u.normalized_claim for u in units if u.claim_type == "failure_mode"]
                )
                output_requirements = _dedupe(
                    [u.normalized_claim for u in units if u.claim_type == "output_contract"]
                )
                trigger_conditions = _dedupe(
                    [u.normalized_claim for u in units if u.claim_type == "trigger_condition"]
                )
                inputs_required = _dedupe(
                    [candidate for candidate in (_extract_inputs_from_claim(u.normalized_claim) for u in units) if candidate]
                )

                if not workflow_steps and not decision_rules and not constraints:
                    emit_stage_log(
                        logger,
                        f"[induce_capabilities] skip group={key} reason=insufficient_executable_content",
                    )
                    continue

                if failure_modes and constraints:
                    risk_class = "high"
                elif failure_modes or len(constraints) >= 2:
                    risk_class = "medium"
                else:
                    risk_class = "low"

                capability = CapabilitySpec(
                    capability_id=capability_id,
                    title=title,
                    domain=str(document.domain or "").strip(),
                    task_family=task_family if task_family != "general" else "",
                    method_family=method_family if method_family != "general" else "",
                    stage=stage,
                    trigger_conditions=trigger_conditions,
                    inputs_required=inputs_required,
                    workflow_steps=workflow_steps,
                    decision_rules=decision_rules,
                    constraints=constraints,
                    failure_modes=failure_modes,
                    output_contract=(
                        {"requirements": output_requirements}
                        if output_requirements
                        else {}
                    ),
                    risk_class=risk_class,
                    evidence_refs=[u.evidence_id for u in units],
                )
                result.capabilities.append(capability)
                emit_stage_log(logger, f"[induce_capabilities] capability={capability.capability_id} evidence={len(units)}")
            except Exception as e:
                result.errors.append({"group": str(key), "error": str(e)})
                emit_stage_log(logger, f"[induce_capabilities] error group={key}: {e}")
        return result

    def _mark_conflicts(self, units: List[EvidenceUnit]) -> None:
        """Annotates evidence units with coarse conflict ids."""

        by_doc: Dict[str, List[EvidenceUnit]] = {}
        for unit in units:
            by_doc.setdefault(unit.doc_id, []).append(unit)
        for bucket in by_doc.values():
            for i, left in enumerate(bucket):
                for right in bucket[i + 1 :]:
                    if not _looks_conflicting(left, right):
                        continue
                    if right.evidence_id not in left.conflicts_with:
                        left.conflicts_with.append(right.evidence_id)
                    if left.evidence_id not in right.conflicts_with:
                        right.conflicts_with.append(left.evidence_id)


def build_capability_inducer(kind: str = "heuristic") -> CapabilityInducer:
    """Builds a concrete capability inducer implementation."""

    name = str(kind or "").strip().lower() or "heuristic"
    if name in {"heuristic", "stub", "rule-based", "rule_based"}:
        return HeuristicCapabilityInducer()
    raise ValueError(f"unsupported capability inducer: {kind}")


def induce_capabilities(
    *,
    documents: List[DocumentRecord],
    evidence_units: List[EvidenceUnit],
    inducer: Optional[CapabilityInducer] = None,
    logger: StageLogger = None,
) -> CapabilityInductionResult:
    """Public functional wrapper for the capability induction stage."""

    impl = inducer or HeuristicCapabilityInducer()
    return impl.induce(
        documents=list(documents or []),
        evidence_units=list(evidence_units or []),
        logger=logger,
    )
