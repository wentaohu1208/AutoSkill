"""
Core data models for the document offline pipeline.

These models define the source-of-truth layers for document ingestion:
- DocumentRecord: normalized imported document payload
- EvidenceUnit: atomic evidence extracted from document spans
- CapabilitySpec: reusable executable capability built from evidence
- SkillSpec: compiled skill artifact derived from a capability
- SkillLifecycle: state transition record for a compiled skill/capability

The models are intentionally domain-agnostic. Domain is treated as metadata
rather than a hard-coded schema branch so the same pipeline can support
psychology, chemistry, geography, and other corpora.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
import json
import re
from typing import Any, Dict, List, Optional, Type, TypeVar

from autoskill.utils.time import now_iso

T = TypeVar("T", bound="SerializableModel")

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _to_plain_data(value: Any) -> Any:
    """Converts dataclasses/enums/nested containers into JSON-safe plain data."""

    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        out: Dict[str, Any] = {}
        for f in fields(value):
            out[f.name] = _to_plain_data(getattr(value, f.name))
        return out
    if isinstance(value, dict):
        return {str(k): _to_plain_data(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_plain_data(v) for v in value]
    return value


def _yaml_scalar(value: Any) -> str:
    """Renders one YAML scalar without requiring PyYAML."""

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value)
    if "\n" in s:
        return ""
    if not s:
        return '""'
    if re.search(r"[:#\[\]\{\},&*!|>'\"%@`]", s) or s.strip() != s:
        return json.dumps(s, ensure_ascii=False)
    low = s.lower()
    if low in {"true", "false", "null", "~"}:
        return json.dumps(s, ensure_ascii=False)
    return s


def _to_yaml_lines(value: Any, *, indent: int = 0) -> List[str]:
    """Serializes plain data to a small YAML subset."""

    space = " " * indent
    if isinstance(value, dict):
        lines: List[str] = []
        for key, item in value.items():
            key_s = str(key)
            if isinstance(item, str) and "\n" in item:
                lines.append(f"{space}{key_s}: |-")
                for ln in item.splitlines():
                    lines.append(f"{space}  {ln}")
                if not item.splitlines():
                    lines.append(f"{space}  ")
                continue
            if isinstance(item, (dict, list)):
                lines.append(f"{space}{key_s}:")
                lines.extend(_to_yaml_lines(item, indent=indent + 2))
                continue
            lines.append(f"{space}{key_s}: {_yaml_scalar(item)}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, str) and "\n" in item:
                lines.append(f"{space}- |-")
                for ln in item.splitlines():
                    lines.append(f"{space}  {ln}")
                if not item.splitlines():
                    lines.append(f"{space}  ")
                continue
            if isinstance(item, (dict, list)):
                lines.append(f"{space}-")
                lines.extend(_to_yaml_lines(item, indent=indent + 2))
                continue
            lines.append(f"{space}- {_yaml_scalar(item)}")
        return lines
    return [f"{space}{_yaml_scalar(value)}"]


def _coerce_str_list(raw: Any) -> List[str]:
    """Normalizes arbitrary list-like content into stripped string lists."""

    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        out = [str(v).strip() for v in raw if str(v).strip()]
        return out
    s = str(raw).strip()
    return [s] if s else []


def _coerce_str_dict(raw: Any) -> Dict[str, Any]:
    """Normalizes arbitrary mapping-like content into a mutable dict."""

    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items()}
    return {}


def _validate_semver(version: str, *, field_name: str) -> None:
    """Checks a semver-like string in MAJOR.MINOR.PATCH form."""

    if not _SEMVER_RE.match(str(version or "").strip()):
        raise ValueError(f"{field_name} must use semantic version format like 0.1.0")


def _validate_confidence(confidence: float, *, field_name: str = "confidence") -> None:
    """Checks that confidence scores stay within [0.0, 1.0]."""

    value = float(confidence)
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")


class SerializableModel:
    """Small mixin for dataclass-backed JSON/YAML serialization."""

    def to_dict(self) -> Dict[str, Any]:
        """Returns a recursive plain-data representation."""

        return _to_plain_data(self)

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        """Serializes the model to a JSON string."""

        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            indent=indent,
            sort_keys=False,
        )

    def to_yaml(self) -> str:
        """Serializes the model to a YAML string without external dependencies."""

        return "\n".join(_to_yaml_lines(self.to_dict())) + "\n"

    @classmethod
    def from_json(cls: Type[T], text: str) -> T:
        """Deserializes the model from a JSON string."""

        obj = json.loads(str(text or "").strip() or "{}")
        if not isinstance(obj, dict):
            raise ValueError("JSON payload must decode into an object")
        return cls.from_dict(obj)

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Builds the model from a plain dict."""

        raise NotImplementedError

    def validate(self) -> None:
        """Runs local invariants. Subclasses should override."""

        return None


class VersionState(str, Enum):
    """Lifecycle state for compiled skills and their registry records."""

    CANDIDATE = "candidate"
    DRAFT = "draft"
    EVALUATING = "evaluating"
    ACTIVE = "active"
    WATCHLIST = "watchlist"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


def _coerce_version_state(value: Any, *, default: VersionState) -> VersionState:
    """Parses lifecycle state strings into VersionState values."""

    if isinstance(value, VersionState):
        return value
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    try:
        return VersionState(raw)
    except ValueError as e:
        raise ValueError(f"invalid lifecycle state: {value}") from e


@dataclass
class TextSpan(SerializableModel):
    """Inclusive-exclusive text span describing a segment within a document."""

    start: int = 0
    end: int = 0

    def __post_init__(self) -> None:
        """Normalizes and validates numeric span boundaries."""

        self.start = int(self.start or 0)
        self.end = int(self.end or 0)
        self.validate()

    def validate(self) -> None:
        """Ensures span offsets are non-negative and ordered."""

        if self.start < 0 or self.end < 0:
            raise ValueError("span offsets must be non-negative")
        if self.end < self.start:
            raise ValueError("span.end must be greater than or equal to span.start")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextSpan":
        """Builds a TextSpan from a plain dict."""

        return cls(start=int(data.get("start", 0) or 0), end=int(data.get("end", 0) or 0))


@dataclass
class DocumentSection(SerializableModel):
    """Named document section used to preserve structure after import."""

    heading: str
    text: str
    level: int = 1
    span: TextSpan = field(default_factory=TextSpan)

    def __post_init__(self) -> None:
        """Normalizes section fields and validates them."""

        self.heading = str(self.heading or "").strip()
        self.text = str(self.text or "")
        self.level = int(self.level or 1)
        if not isinstance(self.span, TextSpan):
            self.span = TextSpan.from_dict(_coerce_str_dict(self.span))
        self.validate()

    def validate(self) -> None:
        """Ensures section payloads remain structurally usable."""

        if not self.text.strip():
            raise ValueError("document section text must not be empty")
        if self.level <= 0:
            raise ValueError("document section level must be positive")
        self.span.validate()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentSection":
        """Builds a DocumentSection from a plain dict."""

        return cls(
            heading=str(data.get("heading") or "").strip(),
            text=str(data.get("text") or ""),
            level=int(data.get("level", 1) or 1),
            span=TextSpan.from_dict(_coerce_str_dict(data.get("span"))),
        )


@dataclass
class ProvenanceRecord(SerializableModel):
    """Source trace explaining where an evidence unit came from."""

    source_type: str = ""
    source_file: str = ""
    section: str = ""
    span: TextSpan = field(default_factory=TextSpan)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalizes provenance fields and validates embedded span data."""

        self.source_type = str(self.source_type or "").strip()
        self.source_file = str(self.source_file or "").strip()
        self.section = str(self.section or "").strip()
        self.metadata = _coerce_str_dict(self.metadata)
        if not isinstance(self.span, TextSpan):
            self.span = TextSpan.from_dict(_coerce_str_dict(self.span))
        self.validate()

    def validate(self) -> None:
        """Ensures a provenance record points to at least one concrete source."""

        if not self.source_type and not self.source_file and not self.section:
            raise ValueError("provenance must include at least one source locator")
        self.span.validate()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProvenanceRecord":
        """Builds a ProvenanceRecord from a plain dict."""

        return cls(
            source_type=str(data.get("source_type") or "").strip(),
            source_file=str(data.get("source_file") or "").strip(),
            section=str(data.get("section") or "").strip(),
            span=TextSpan.from_dict(_coerce_str_dict(data.get("span"))),
            metadata=_coerce_str_dict(data.get("metadata")),
        )


@dataclass
class DocumentRecord(SerializableModel):
    """Normalized offline document payload and its import metadata."""

    doc_id: str
    source_type: str
    title: str
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    domain: str = ""
    raw_text: str = ""
    sections: List[DocumentSection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    checksum: str = ""
    content_hash: str = ""
    imported_at: str = ""

    def __post_init__(self) -> None:
        """Normalizes document fields and fills stable defaults."""

        self.doc_id = str(self.doc_id or "").strip()
        self.source_type = str(self.source_type or "").strip()
        self.title = str(self.title or "").strip()
        self.authors = _coerce_str_list(self.authors)
        self.year = int(self.year) if self.year is not None and str(self.year).strip() else None
        self.domain = str(self.domain or "").strip()
        self.raw_text = str(self.raw_text or "")
        self.sections = [
            sec if isinstance(sec, DocumentSection) else DocumentSection.from_dict(_coerce_str_dict(sec))
            for sec in list(self.sections or [])
        ]
        self.metadata = _coerce_str_dict(self.metadata)
        self.checksum = str(self.checksum or "").strip()
        self.content_hash = str(self.content_hash or "").strip()
        if self.checksum and not self.content_hash:
            self.content_hash = self.checksum
        if self.content_hash and not self.checksum:
            self.checksum = self.content_hash
        self.imported_at = str(self.imported_at or "").strip() or now_iso()
        self.validate()

    def validate(self) -> None:
        """Ensures imported document records contain enough identity and content."""

        if not self.doc_id:
            raise ValueError("doc_id must not be empty")
        if not self.source_type:
            raise ValueError("source_type must not be empty")
        if not self.title:
            raise ValueError("title must not be empty")
        if self.year is not None and (self.year < 0 or self.year > 9999):
            raise ValueError("year must be between 0 and 9999")
        if not self.raw_text.strip() and not self.sections:
            raise ValueError("document must contain raw_text or at least one section")
        if not self.content_hash:
            raise ValueError("content_hash/checksum must not be empty")
        for section in self.sections:
            section.validate()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentRecord":
        """Builds a DocumentRecord from a plain dict."""

        return cls(
            doc_id=str(data.get("doc_id") or "").strip(),
            source_type=str(data.get("source_type") or "").strip(),
            title=str(data.get("title") or "").strip(),
            authors=_coerce_str_list(data.get("authors")),
            year=data.get("year"),
            domain=str(data.get("domain") or "").strip(),
            raw_text=str(data.get("raw_text") or ""),
            sections=[
                DocumentSection.from_dict(_coerce_str_dict(item))
                for item in list(data.get("sections") or [])
            ],
            metadata=_coerce_str_dict(data.get("metadata")),
            checksum=str(data.get("checksum") or "").strip(),
            content_hash=str(data.get("content_hash") or "").strip(),
            imported_at=str(data.get("imported_at") or "").strip(),
        )


@dataclass
class EvidenceUnit(SerializableModel):
    """Atomic evidence statement extracted from a document span."""

    evidence_id: str
    doc_id: str
    claim_type: str
    section: str = ""
    span: TextSpan = field(default_factory=TextSpan)
    normalized_claim: str = ""
    verbatim_excerpt: str = ""
    method_family: str = ""
    task_family: str = ""
    confidence: float = 0.0
    conflicts_with: List[str] = field(default_factory=list)
    provenance: ProvenanceRecord = field(default_factory=lambda: ProvenanceRecord(source_type="document"))

    def __post_init__(self) -> None:
        """Normalizes evidence fields and validates core extraction invariants."""

        self.evidence_id = str(self.evidence_id or "").strip()
        self.doc_id = str(self.doc_id or "").strip()
        self.claim_type = str(self.claim_type or "").strip()
        self.section = str(self.section or "").strip()
        if not isinstance(self.span, TextSpan):
            self.span = TextSpan.from_dict(_coerce_str_dict(self.span))
        self.normalized_claim = str(self.normalized_claim or "").strip()
        self.verbatim_excerpt = str(self.verbatim_excerpt or "")
        self.method_family = str(self.method_family or "").strip()
        self.task_family = str(self.task_family or "").strip()
        self.confidence = float(self.confidence or 0.0)
        self.conflicts_with = _coerce_str_list(self.conflicts_with)
        if not isinstance(self.provenance, ProvenanceRecord):
            prov = _coerce_str_dict(self.provenance)
            if not prov and self.section:
                prov = {"section": self.section, "source_type": "document"}
            self.provenance = ProvenanceRecord.from_dict(prov or {"source_type": "document"})
        self.validate()

    def validate(self) -> None:
        """Ensures evidence remains grounded in a concrete source and claim."""

        if not self.evidence_id:
            raise ValueError("evidence_id must not be empty")
        if not self.doc_id:
            raise ValueError("doc_id must not be empty")
        if not self.claim_type:
            raise ValueError("claim_type must not be empty")
        if not self.normalized_claim:
            raise ValueError("normalized_claim must not be empty")
        _validate_confidence(self.confidence)
        self.span.validate()
        self.provenance.validate()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceUnit":
        """Builds an EvidenceUnit from a plain dict."""

        return cls(
            evidence_id=str(data.get("evidence_id") or "").strip(),
            doc_id=str(data.get("doc_id") or "").strip(),
            claim_type=str(data.get("claim_type") or "").strip(),
            section=str(data.get("section") or "").strip(),
            span=TextSpan.from_dict(_coerce_str_dict(data.get("span"))),
            normalized_claim=str(data.get("normalized_claim") or "").strip(),
            verbatim_excerpt=str(data.get("verbatim_excerpt") or ""),
            method_family=str(data.get("method_family") or "").strip(),
            task_family=str(data.get("task_family") or "").strip(),
            confidence=float(data.get("confidence", 0.0) or 0.0),
            conflicts_with=_coerce_str_list(data.get("conflicts_with")),
            provenance=ProvenanceRecord.from_dict(
                _coerce_str_dict(data.get("provenance")) or {"source_type": "document"}
            ),
        )


@dataclass
class CapabilitySpec(SerializableModel):
    """Reusable executable capability distilled from one or more evidence units."""

    capability_id: str
    title: str
    domain: str = ""
    task_family: str = ""
    method_family: str = ""
    stage: str = ""
    trigger_conditions: List[str] = field(default_factory=list)
    inputs_required: List[str] = field(default_factory=list)
    workflow_steps: List[str] = field(default_factory=list)
    decision_rules: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    failure_modes: List[str] = field(default_factory=list)
    output_contract: Dict[str, Any] = field(default_factory=dict)
    risk_class: str = ""
    evidence_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: str = "0.1.0"
    status: VersionState = VersionState.CANDIDATE

    def __post_init__(self) -> None:
        """Normalizes capability fields and validates registry-level invariants."""

        self.capability_id = str(self.capability_id or "").strip()
        self.title = str(self.title or "").strip()
        self.domain = str(self.domain or "").strip()
        self.task_family = str(self.task_family or "").strip()
        self.method_family = str(self.method_family or "").strip()
        self.stage = str(self.stage or "").strip()
        self.trigger_conditions = _coerce_str_list(self.trigger_conditions)
        self.inputs_required = _coerce_str_list(self.inputs_required)
        self.workflow_steps = _coerce_str_list(self.workflow_steps)
        self.decision_rules = _coerce_str_list(self.decision_rules)
        self.constraints = _coerce_str_list(self.constraints)
        self.failure_modes = _coerce_str_list(self.failure_modes)
        self.output_contract = _coerce_str_dict(self.output_contract)
        self.risk_class = str(self.risk_class or "").strip()
        self.evidence_refs = _coerce_str_list(self.evidence_refs)
        self.metadata = _coerce_str_dict(self.metadata)
        self.version = str(self.version or "").strip() or "0.1.0"
        self.status = _coerce_version_state(self.status, default=VersionState.CANDIDATE)
        self.validate()

    def validate(self) -> None:
        """Ensures capabilities remain evidence-backed and versioned."""

        if not self.capability_id:
            raise ValueError("capability_id must not be empty")
        if not self.title:
            raise ValueError("capability title must not be empty")
        if not self.workflow_steps and not self.decision_rules and not self.constraints:
            raise ValueError(
                "capability must include workflow_steps, decision_rules, or constraints"
            )
        if not self.evidence_refs:
            raise ValueError("capability must reference at least one evidence unit")
        _validate_semver(self.version, field_name="version")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CapabilitySpec":
        """Builds a CapabilitySpec from a plain dict."""

        return cls(
            capability_id=str(data.get("capability_id") or "").strip(),
            title=str(data.get("title") or "").strip(),
            domain=str(data.get("domain") or "").strip(),
            task_family=str(data.get("task_family") or "").strip(),
            method_family=str(data.get("method_family") or "").strip(),
            stage=str(data.get("stage") or "").strip(),
            trigger_conditions=_coerce_str_list(data.get("trigger_conditions")),
            inputs_required=_coerce_str_list(data.get("inputs_required")),
            workflow_steps=_coerce_str_list(data.get("workflow_steps")),
            decision_rules=_coerce_str_list(data.get("decision_rules")),
            constraints=_coerce_str_list(data.get("constraints")),
            failure_modes=_coerce_str_list(data.get("failure_modes")),
            output_contract=_coerce_str_dict(data.get("output_contract")),
            risk_class=str(data.get("risk_class") or "").strip(),
            evidence_refs=_coerce_str_list(data.get("evidence_refs")),
            metadata=_coerce_str_dict(data.get("metadata")),
            version=str(data.get("version") or "0.1.0"),
            status=data.get("status") or VersionState.CANDIDATE.value,
        )


@dataclass
class SkillSpec(SerializableModel):
    """Compiled skill representation derived from a capability specification."""

    skill_id: str
    capability_id: str
    name: str
    description: str
    skill_body: str
    references: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: str = "0.1.0"
    status: VersionState = VersionState.DRAFT

    def __post_init__(self) -> None:
        """Normalizes compiled skill fields and validates state."""

        self.skill_id = str(self.skill_id or "").strip()
        self.capability_id = str(self.capability_id or "").strip()
        self.name = str(self.name or "").strip()
        self.description = str(self.description or "").strip()
        self.skill_body = str(self.skill_body or "")
        self.references = _coerce_str_list(self.references)
        self.metadata = _coerce_str_dict(self.metadata)
        self.version = str(self.version or "").strip() or "0.1.0"
        self.status = _coerce_version_state(self.status, default=VersionState.DRAFT)
        self.validate()

    def validate(self) -> None:
        """Ensures compiled skills retain stable identity and body content."""

        if not self.skill_id:
            raise ValueError("skill_id must not be empty")
        if not self.capability_id:
            raise ValueError("capability_id must not be empty")
        if not self.name:
            raise ValueError("skill name must not be empty")
        if not self.description:
            raise ValueError("skill description must not be empty")
        if not self.skill_body.strip():
            raise ValueError("skill_body must not be empty")
        _validate_semver(self.version, field_name="version")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillSpec":
        """Builds a SkillSpec from a plain dict."""

        return cls(
            skill_id=str(data.get("skill_id") or "").strip(),
            capability_id=str(data.get("capability_id") or "").strip(),
            name=str(data.get("name") or "").strip(),
            description=str(data.get("description") or "").strip(),
            skill_body=str(data.get("skill_body") or ""),
            references=_coerce_str_list(data.get("references")),
            metadata=_coerce_str_dict(data.get("metadata")),
            version=str(data.get("version") or "0.1.0"),
            status=data.get("status") or VersionState.DRAFT.value,
        )


@dataclass
class SkillLifecycle(SerializableModel):
    """Lifecycle transition for a skill or capability within the offline registry."""

    lifecycle_id: str
    skill_id: str = ""
    capability_id: str = ""
    from_state: Optional[VersionState] = None
    to_state: VersionState = VersionState.CANDIDATE
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    changed_at: str = ""

    def __post_init__(self) -> None:
        """Normalizes transition fields and validates state changes."""

        self.lifecycle_id = str(self.lifecycle_id or "").strip()
        self.skill_id = str(self.skill_id or "").strip()
        self.capability_id = str(self.capability_id or "").strip()
        if self.from_state is not None:
            self.from_state = _coerce_version_state(self.from_state, default=VersionState.CANDIDATE)
        self.to_state = _coerce_version_state(self.to_state, default=VersionState.CANDIDATE)
        self.reason = str(self.reason or "").strip()
        self.metadata = _coerce_str_dict(self.metadata)
        self.changed_at = str(self.changed_at or "").strip() or now_iso()
        self.validate()

    def validate(self) -> None:
        """Ensures lifecycle entries identify a target entity and a valid transition."""

        if not self.lifecycle_id:
            raise ValueError("lifecycle_id must not be empty")
        if not self.skill_id and not self.capability_id:
            raise ValueError("lifecycle must reference skill_id or capability_id")
        if self.from_state is not None and self.from_state == self.to_state:
            raise ValueError("lifecycle transition must change state when from_state is set")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillLifecycle":
        """Builds a SkillLifecycle from a plain dict."""

        raw_from = data.get("from_state")
        return cls(
            lifecycle_id=str(data.get("lifecycle_id") or "").strip(),
            skill_id=str(data.get("skill_id") or "").strip(),
            capability_id=str(data.get("capability_id") or "").strip(),
            from_state=(
                _coerce_version_state(raw_from, default=VersionState.CANDIDATE)
                if raw_from is not None and str(raw_from).strip()
                else None
            ),
            to_state=data.get("to_state") or VersionState.CANDIDATE.value,
            reason=str(data.get("reason") or "").strip(),
            metadata=_coerce_str_dict(data.get("metadata")),
            changed_at=str(data.get("changed_at") or "").strip(),
        )
