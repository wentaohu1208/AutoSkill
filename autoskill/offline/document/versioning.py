"""
Registry/version registration stage for the offline document pipeline.

This module keeps lifecycle and version reasoning capability-centric:
- capability similarity and structure drive change classification
- skill versions derive from capability versions
- registry receives version history, change logs, provenance links, and lifecycle
  state transitions
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from autoskill import AutoSkill

from .common import StageLogger, emit_stage_log, normalize_text
from .compiler import skill_spec_to_candidate
from .models import (
    CapabilitySpec,
    DocumentRecord,
    EvidenceUnit,
    SkillLifecycle,
    SkillSpec,
    VersionState,
)
from .prompt_runtime import activate_offline_prompt_runtime
from .registry import DocumentRegistry
from autoskill.utils.time import now_iso

_TOKEN_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]+")
_ACTIVE_STORE_STATES = {
    VersionState.CANDIDATE,
    VersionState.DRAFT,
    VersionState.EVALUATING,
    VersionState.ACTIVE,
    VersionState.WATCHLIST,
}
def _token_set(text: str) -> Set[str]:
    """Builds a token set for coarse semantic overlap checks."""

    return {m.group(0) for m in _TOKEN_RE.finditer(normalize_text(text, lower=True))}


def _jaccard_text(left: str, right: str) -> float:
    """Returns token-overlap similarity for two text snippets."""

    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    union = left_tokens | right_tokens
    if not union:
        return 0.0
    return float(len(left_tokens & right_tokens)) / float(len(union))


def _list_similarity(left: Iterable[str], right: Iterable[str]) -> float:
    """Returns similarity between two ordered string lists."""

    left_joined = "\n".join(str(item or "").strip() for item in list(left or []) if str(item or "").strip())
    right_joined = "\n".join(str(item or "").strip() for item in list(right or []) if str(item or "").strip())
    if not left_joined and not right_joined:
        return 1.0
    return _jaccard_text(left_joined, right_joined)


def _dict_similarity(left: Dict[str, Any], right: Dict[str, Any]) -> float:
    """Returns coarse similarity between two dict-like payloads."""

    return _jaccard_text(
        json.dumps(dict(left or {}), ensure_ascii=False, sort_keys=True),
        json.dumps(dict(right or {}), ensure_ascii=False, sort_keys=True),
    )


def _family_similarity(left: CapabilitySpec, right: CapabilitySpec) -> float:
    """Returns similarity across domain/task/method/stage family labels."""

    pairs = [
        (left.domain, right.domain),
        (left.task_family, right.task_family),
        (left.method_family, right.method_family),
        (left.stage, right.stage),
    ]
    considered = 0
    matched = 0
    for left_value, right_value in pairs:
        left_s = str(left_value or "").strip().lower()
        right_s = str(right_value or "").strip().lower()
        if not left_s and not right_s:
            continue
        considered += 1
        if left_s == right_s:
            matched += 1
    if considered <= 0:
        return 0.0
    return float(matched) / float(considered)


def _bump_patch(version: str) -> str:
    """Bumps a semantic version patch number."""

    parts = [p for p in str(version or "").split(".") if p.strip().isdigit()]
    if len(parts) != 3:
        return "0.1.1"
    major, minor, patch = (int(parts[0]), int(parts[1]), int(parts[2]))
    return f"{major}.{minor}.{patch + 1}"


def _signature(obj: Any, *, exclude: Optional[Set[str]] = None) -> str:
    """Builds a stable comparison signature from a serializable model."""

    exclude_keys = set(exclude or set())
    if hasattr(obj, "to_dict"):
        payload = obj.to_dict()
    elif isinstance(obj, dict):
        payload = dict(obj)
    else:
        raise ValueError("signature input must be dict-like or expose to_dict()")

    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(k): clean(v)
                for k, v in value.items()
                if str(k) not in exclude_keys
            }
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value

    return json.dumps(clean(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _plain_skill(skill: Any) -> Dict[str, Any]:
    """Serializes one persisted AutoSkill store record into a compact dict."""

    return {
        "id": str(getattr(skill, "id", "") or ""),
        "name": str(getattr(skill, "name", "") or ""),
        "description": str(getattr(skill, "description", "") or ""),
        "version": str(getattr(skill, "version", "") or ""),
        "status": str(getattr(getattr(skill, "status", None), "value", getattr(skill, "status", "")) or ""),
    }


def _copy_capability(
    capability: CapabilitySpec,
    *,
    capability_id: Optional[str] = None,
    version: Optional[str] = None,
    status: Optional[VersionState] = None,
    metadata_update: Optional[Dict[str, Any]] = None,
) -> CapabilitySpec:
    """Creates a capability copy with updated identity/version/status fields."""

    payload = capability.to_dict()
    if capability_id is not None:
        payload["capability_id"] = str(capability_id or "").strip()
    if version is not None:
        payload["version"] = str(version or "0.1.0")
    if status is not None:
        payload["status"] = status.value
    md = dict(payload.get("metadata") or {})
    if metadata_update:
        md.update(dict(metadata_update or {}))
    payload["metadata"] = md
    return CapabilitySpec.from_dict(payload)


def _copy_skill(
    skill: SkillSpec,
    *,
    skill_id: Optional[str] = None,
    capability_id: Optional[str] = None,
    version: Optional[str] = None,
    status: Optional[VersionState] = None,
    metadata_update: Optional[Dict[str, Any]] = None,
) -> SkillSpec:
    """Creates a skill copy with updated identity/version/status fields."""

    payload = skill.to_dict()
    if skill_id is not None:
        payload["skill_id"] = str(skill_id or "").strip()
    if capability_id is not None:
        payload["capability_id"] = str(capability_id or "").strip()
    if version is not None:
        payload["version"] = str(version or "0.1.0")
    if status is not None:
        payload["status"] = status.value
    md = dict(payload.get("metadata") or {})
    if metadata_update:
        md.update(dict(metadata_update or {}))
    payload["metadata"] = md
    return SkillSpec.from_dict(payload)


def _skill_id_for_capability(capability_id: str) -> str:
    """Builds the default deterministic skill id for one capability id."""

    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"autoskill-skill-spec:{capability_id}"))


def _evidence_lookup(
    registry: DocumentRegistry,
    evidence_units: Sequence[EvidenceUnit],
) -> Dict[str, EvidenceUnit]:
    """Builds a combined evidence index from registry state and current batch."""

    out = {
        unit.evidence_id: unit
        for unit in registry.list_evidence()
    }
    for unit in evidence_units or []:
        out[unit.evidence_id] = unit
    return out


def _doc_ids_from_evidence(evidence_ids: Sequence[str], evidence_by_id: Dict[str, EvidenceUnit]) -> List[str]:
    """Collects source document ids for one evidence reference set."""

    seen = set()
    out: List[str] = []
    for evidence_id in evidence_ids or []:
        unit = evidence_by_id.get(str(evidence_id or "").strip())
        if unit is None:
            continue
        doc_id = str(unit.doc_id or "").strip()
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        out.append(doc_id)
    return out


def _conflicting_evidence_ids(evidence_ids: Sequence[str], evidence_by_id: Dict[str, EvidenceUnit]) -> List[str]:
    """Collects evidence ids that carry conflicts."""

    out: List[str] = []
    seen = set()
    for evidence_id in evidence_ids or []:
        unit = evidence_by_id.get(str(evidence_id or "").strip())
        if unit is None:
            continue
        if not list(unit.conflicts_with or []):
            continue
        if unit.evidence_id in seen:
            continue
        seen.add(unit.evidence_id)
        out.append(unit.evidence_id)
    return out


def _first_skill_for_capability(
    skills_by_capability_id: Dict[str, List[SkillSpec]],
    capability_id: str,
) -> Optional[SkillSpec]:
    """Returns the first known skill for one capability id."""

    bucket = list(skills_by_capability_id.get(str(capability_id or "").strip(), []) or [])
    return bucket[0] if bucket else None


@dataclass
class CapabilityDiff:
    """Structured diff between a candidate capability and one existing capability."""

    candidate_capability_id: str
    existing_capability_id: str
    title_similarity: float = 0.0
    workflow_similarity: float = 0.0
    family_similarity: float = 0.0
    structure_similarity: float = 0.0
    overall_similarity: float = 0.0
    evidence_added: List[str] = field(default_factory=list)
    evidence_removed: List[str] = field(default_factory=list)
    conflicting_evidence: List[str] = field(default_factory=list)
    doc_ids: List[str] = field(default_factory=list)


@dataclass
class ChangeDecision:
    """Decision returned by capability change classification."""

    action: str
    capability: CapabilitySpec
    matched_capability_ids: List[str] = field(default_factory=list)
    reason: str = ""
    diffs: List[CapabilityDiff] = field(default_factory=list)
    split_parent_id: str = ""


@dataclass
class VersionRegistrationResult:
    """Output of the registry/version registration stage."""

    documents: List[DocumentRecord] = field(default_factory=list)
    evidence_units: List[EvidenceUnit] = field(default_factory=list)
    capabilities: List[CapabilitySpec] = field(default_factory=list)
    skill_specs: List[SkillSpec] = field(default_factory=list)
    lifecycles: List[SkillLifecycle] = field(default_factory=list)
    change_logs: List[Dict[str, Any]] = field(default_factory=list)
    version_history: List[Dict[str, Any]] = field(default_factory=list)
    provenance_links: List[Dict[str, Any]] = field(default_factory=list)
    upserted_store_skills: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)
    dry_run: bool = False


class VersionManager:
    """Capability-centric version and lifecycle manager for document builds."""

    def __init__(
        self,
        *,
        registry: DocumentRegistry,
        logger: StageLogger = None,
    ) -> None:
        """Initializes the version manager with registry-backed context."""

        self.registry = registry
        self.logger = logger

    def diff_capability(
        self,
        candidate: CapabilitySpec,
        existing: CapabilitySpec,
        *,
        evidence_by_id: Dict[str, EvidenceUnit],
    ) -> CapabilityDiff:
        """Computes structural and provenance-aware similarity for two capabilities."""

        title_similarity = _jaccard_text(candidate.title, existing.title)
        workflow_similarity = _list_similarity(candidate.workflow_steps, existing.workflow_steps)
        family_similarity = _family_similarity(candidate, existing)
        structure_similarity = (
            0.40 * _list_similarity(candidate.decision_rules, existing.decision_rules)
            + 0.30 * _list_similarity(candidate.constraints, existing.constraints)
            + 0.15 * _list_similarity(candidate.failure_modes, existing.failure_modes)
            + 0.15 * _dict_similarity(candidate.output_contract, existing.output_contract)
        )
        overall_similarity = (
            0.30 * title_similarity
            + 0.35 * workflow_similarity
            + 0.20 * family_similarity
            + 0.15 * structure_similarity
        )
        candidate_refs = set(candidate.evidence_refs or [])
        existing_refs = set(existing.evidence_refs or [])
        evidence_added = sorted(candidate_refs - existing_refs)
        evidence_removed = sorted(existing_refs - candidate_refs)
        conflict_candidates = _conflicting_evidence_ids(
            list(candidate_refs | existing_refs),
            evidence_by_id,
        )
        doc_ids = _doc_ids_from_evidence(sorted(candidate_refs | existing_refs), evidence_by_id)
        return CapabilityDiff(
            candidate_capability_id=candidate.capability_id,
            existing_capability_id=existing.capability_id,
            title_similarity=title_similarity,
            workflow_similarity=workflow_similarity,
            family_similarity=family_similarity,
            structure_similarity=structure_similarity,
            overall_similarity=overall_similarity,
            evidence_added=evidence_added,
            evidence_removed=evidence_removed,
            conflicting_evidence=conflict_candidates,
            doc_ids=doc_ids,
        )

    def classify_change(
        self,
        capability: CapabilitySpec,
        *,
        existing_capabilities: Sequence[CapabilitySpec],
        evidence_by_id: Dict[str, EvidenceUnit],
    ) -> ChangeDecision:
        """Classifies one candidate capability against registry state."""

        diffs = sorted(
            [
                self.diff_capability(capability, existing, evidence_by_id=evidence_by_id)
                for existing in list(existing_capabilities or [])
            ],
            key=lambda item: (
                item.overall_similarity,
                item.workflow_similarity,
                item.title_similarity,
                item.family_similarity,
            ),
            reverse=True,
        )
        if not diffs:
            return ChangeDecision(action="create", capability=capability, reason="no_existing_capabilities")

        merge_diffs = [
            diff
            for diff in diffs
            if diff.overall_similarity >= 0.72
            and (diff.title_similarity >= 0.50 or diff.family_similarity >= 0.66)
        ]
        if len(merge_diffs) >= 2:
            return ChangeDecision(
                action="merge",
                capability=capability,
                matched_capability_ids=[diff.existing_capability_id for diff in merge_diffs],
                reason="multiple_existing_capabilities_highly_overlap",
                diffs=merge_diffs,
            )

        best = diffs[0]
        if best.overall_similarity < 0.55:
            return ChangeDecision(
                action="create",
                capability=capability,
                reason="no_close_existing_capability",
                diffs=[best],
            )

        if (
            best.overall_similarity >= 0.65
            and best.family_similarity >= 0.66
            and best.workflow_similarity < 0.50
        ):
            return ChangeDecision(
                action="revise",
                capability=capability,
                matched_capability_ids=[best.existing_capability_id],
                reason="same_family_but_workflow_diverged",
                diffs=[best],
                split_parent_id=best.existing_capability_id,
            )

        if (
            best.overall_similarity >= 0.82
            and best.workflow_similarity >= 0.82
            and not best.evidence_removed
            and not best.conflicting_evidence
            and list(best.evidence_added or [])
        ):
            return ChangeDecision(
                action="strengthen",
                capability=capability,
                matched_capability_ids=[best.existing_capability_id],
                reason="evidence_added_without_structural_regression",
                diffs=[best],
            )

        if (
            _signature(capability, exclude={"version", "status", "metadata"})
            == _signature(
                next(existing for existing in existing_capabilities if existing.capability_id == best.existing_capability_id),
                exclude={"version", "status", "metadata"},
            )
        ):
            return ChangeDecision(
                action="unchanged",
                capability=capability,
                matched_capability_ids=[best.existing_capability_id],
                reason="identical_capability_signature",
                diffs=[best],
            )

        return ChangeDecision(
            action="revise",
            capability=capability,
            matched_capability_ids=[best.existing_capability_id],
            reason="closest_existing_capability_requires_revision",
            diffs=[best],
        )

    def create_new_version(self, *, current_version: str, action: str) -> str:
        """Creates the next version string for one lifecycle action."""

        action_s = str(action or "").strip().lower()
        if action_s in {"", "create"}:
            return str(current_version or "").strip() or "0.1.0"
        if action_s == "unchanged":
            return str(current_version or "").strip() or "0.1.0"
        return _bump_patch(str(current_version or "").strip() or "0.1.0")

    def update_lifecycle(
        self,
        *,
        skill_id: str = "",
        capability_id: str = "",
        current_state: Optional[VersionState],
        action: str,
        target_state: VersionState,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SkillLifecycle:
        """Creates one lifecycle transition consistent with the requested action."""

        action_s = str(action or "").strip().lower()
        if action_s == "deprecate":
            next_state = target_state if target_state in {VersionState.WATCHLIST, VersionState.DEPRECATED, VersionState.RETIRED} else VersionState.DEPRECATED
        else:
            next_state = target_state
        from_state = current_state if current_state is not None and current_state != next_state else None
        return SkillLifecycle(
            lifecycle_id=str(uuid.uuid4()),
            skill_id=str(skill_id or "").strip(),
            capability_id=str(capability_id or "").strip(),
            from_state=from_state,
            to_state=next_state,
            reason=action_s or "update",
            metadata=dict(metadata or {}),
        )

    def mark_deprecated(
        self,
        *,
        capability: CapabilitySpec,
        skills: Sequence[SkillSpec],
        reason: str,
        state: VersionState = VersionState.DEPRECATED,
        related_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Marks one capability and its compiled skills as deprecated/watchlist/retired."""

        related = list(related_ids or [])
        next_version = self.create_new_version(current_version=capability.version, action="deprecate")
        cap_md = {
            "change_action": "deprecate",
            "deprecation_reason": str(reason or "").strip(),
            "related_capability_ids": related,
        }
        updated_capability = _copy_capability(
            capability,
            version=next_version,
            status=state,
            metadata_update=cap_md,
        )
        updated_skills: List[SkillSpec] = []
        lifecycles: List[SkillLifecycle] = []
        change_logs: List[Dict[str, Any]] = []
        version_history: List[Dict[str, Any]] = []
        provenance_links: List[Dict[str, Any]] = []

        cap_provenance = {
            "entity_type": "capability",
            "entity_id": updated_capability.capability_id,
            "doc_ids": [],
            "evidence_added": [],
            "evidence_removed": [],
            "evidence_conflicts": [],
            "related_entity_ids": related,
        }
        provenance_links.append(cap_provenance)
        version_history.append(
            {
                "entity_type": "capability",
                "entity_id": updated_capability.capability_id,
                "version": updated_capability.version,
                "action": "deprecate",
                "changed_at": now_iso(),
                "status": updated_capability.status.value,
                "related_entity_ids": related,
            }
        )
        change_logs.append(
            {
                "change_id": str(uuid.uuid4()),
                "entity_type": "capability",
                "entity_id": updated_capability.capability_id,
                "action": "deprecate",
                "changed_at": now_iso(),
                "from_version": capability.version,
                "to_version": updated_capability.version,
                "from_state": capability.status.value,
                "to_state": updated_capability.status.value,
                "summary": str(reason or "").strip(),
                "related_entity_ids": related,
                "provenance": cap_provenance,
            }
        )

        for skill in list(skills or []):
            updated_skill = _copy_skill(
                skill,
                version=next_version,
                status=state,
                metadata_update={
                    "change_action": "deprecate",
                    "deprecation_reason": str(reason or "").strip(),
                    "related_capability_ids": related,
                },
            )
            updated_skills.append(updated_skill)
            lifecycles.append(
                self.update_lifecycle(
                    skill_id=updated_skill.skill_id,
                    capability_id=updated_skill.capability_id,
                    current_state=skill.status,
                    action="deprecate",
                    target_state=state,
                    metadata={"reason": str(reason or "").strip(), "related_entity_ids": related},
                )
            )
            skill_provenance = {
                "entity_type": "skill",
                "entity_id": updated_skill.skill_id,
                "doc_ids": [],
                "evidence_added": [],
                "evidence_removed": [],
                "evidence_conflicts": [],
                "related_entity_ids": [updated_capability.capability_id] + related,
            }
            provenance_links.append(skill_provenance)
            version_history.append(
                {
                    "entity_type": "skill",
                    "entity_id": updated_skill.skill_id,
                    "version": updated_skill.version,
                    "action": "deprecate",
                    "changed_at": now_iso(),
                    "status": updated_skill.status.value,
                    "related_entity_ids": [updated_capability.capability_id] + related,
                }
            )
            change_logs.append(
                {
                    "change_id": str(uuid.uuid4()),
                    "entity_type": "skill",
                    "entity_id": updated_skill.skill_id,
                    "action": "deprecate",
                    "changed_at": now_iso(),
                    "from_version": skill.version,
                    "to_version": updated_skill.version,
                    "from_state": skill.status.value,
                    "to_state": updated_skill.status.value,
                    "summary": str(reason or "").strip(),
                    "related_entity_ids": [updated_capability.capability_id] + related,
                    "provenance": skill_provenance,
                }
            )
        return {
            "capability": updated_capability,
            "skills": updated_skills,
            "lifecycles": lifecycles,
            "change_logs": change_logs,
            "version_history": version_history,
            "provenance_links": provenance_links,
        }

    def merge_skills(
        self,
        *,
        decision: ChangeDecision,
        skill: SkillSpec,
        existing_capabilities_by_id: Dict[str, CapabilitySpec],
        existing_skills_by_capability_id: Dict[str, List[SkillSpec]],
        target_state: VersionState,
    ) -> Dict[str, Any]:
        """Merges multiple existing capabilities into one updated primary capability/skill."""

        matched_ids = [cap_id for cap_id in decision.matched_capability_ids if cap_id in existing_capabilities_by_id]
        primary_existing = existing_capabilities_by_id[matched_ids[0]]
        secondary_existing = [existing_capabilities_by_id[cap_id] for cap_id in matched_ids[1:]]
        primary_skill = _first_skill_for_capability(existing_skills_by_capability_id, primary_existing.capability_id)
        next_version = self.create_new_version(current_version=primary_existing.version, action="merge")
        merged_capability = _copy_capability(
            decision.capability,
            capability_id=primary_existing.capability_id,
            version=next_version,
            status=target_state,
            metadata_update={
                "change_action": "merge",
                "merged_from_capability_ids": [cap.capability_id for cap in secondary_existing],
            },
        )
        merged_skill = _copy_skill(
            skill,
            skill_id=(primary_skill.skill_id if primary_skill is not None else _skill_id_for_capability(merged_capability.capability_id)),
            capability_id=merged_capability.capability_id,
            version=merged_capability.version,
            status=target_state,
            metadata_update={
                "change_action": "merge",
                "merged_from_capability_ids": [cap.capability_id for cap in secondary_existing],
            },
        )
        deprecated_secondary: List[Dict[str, Any]] = []
        for secondary in secondary_existing:
            secondary_skills = list(existing_skills_by_capability_id.get(secondary.capability_id, []) or [])
            deprecated_secondary.append(
                self.mark_deprecated(
                    capability=secondary,
                    skills=secondary_skills,
                    reason="merged_into_other_capability",
                    state=VersionState.DEPRECATED,
                    related_ids=[primary_existing.capability_id],
                )
            )
        return {
            "primary_capability": merged_capability,
            "primary_skill": merged_skill,
            "secondary": deprecated_secondary,
        }

    def split_skill(
        self,
        *,
        parent_capability: CapabilitySpec,
        child_capabilities: Sequence[CapabilitySpec],
        child_skills_by_capability_id: Dict[str, SkillSpec],
        existing_skills_by_capability_id: Dict[str, List[SkillSpec]],
        target_state: VersionState,
    ) -> Dict[str, Any]:
        """Splits one existing capability into multiple more focused capabilities/skills."""

        updated_children: List[CapabilitySpec] = []
        updated_child_skills: List[SkillSpec] = []
        lifecycles: List[SkillLifecycle] = []
        change_logs: List[Dict[str, Any]] = []
        version_history: List[Dict[str, Any]] = []
        provenance_links: List[Dict[str, Any]] = []

        for child in list(child_capabilities or []):
            child_capability = _copy_capability(
                child,
                version="0.1.0",
                status=target_state,
                metadata_update={
                    "change_action": "split",
                    "split_from_capability_id": parent_capability.capability_id,
                },
            )
            child_skill = _copy_skill(
                child_skills_by_capability_id[child.capability_id],
                version=child_capability.version,
                status=target_state,
                metadata_update={
                    "change_action": "split",
                    "split_from_capability_id": parent_capability.capability_id,
                },
            )
            updated_children.append(child_capability)
            updated_child_skills.append(child_skill)
            lifecycles.append(
                self.update_lifecycle(
                    skill_id=child_skill.skill_id,
                    capability_id=child_capability.capability_id,
                    current_state=None,
                    action="split",
                    target_state=target_state,
                    metadata={"split_from_capability_id": parent_capability.capability_id},
                )
            )
            provenance = {
                "entity_type": "capability",
                "entity_id": child_capability.capability_id,
                "doc_ids": [],
                "evidence_added": list(child_capability.evidence_refs or []),
                "evidence_removed": [],
                "evidence_conflicts": [],
                "related_entity_ids": [parent_capability.capability_id],
            }
            provenance_links.append(provenance)
            version_history.append(
                {
                    "entity_type": "capability",
                    "entity_id": child_capability.capability_id,
                    "version": child_capability.version,
                    "action": "split",
                    "changed_at": now_iso(),
                    "status": child_capability.status.value,
                    "related_entity_ids": [parent_capability.capability_id],
                }
            )
            version_history.append(
                {
                    "entity_type": "skill",
                    "entity_id": child_skill.skill_id,
                    "version": child_skill.version,
                    "action": "split",
                    "changed_at": now_iso(),
                    "status": child_skill.status.value,
                    "related_entity_ids": [parent_capability.capability_id],
                }
            )
            change_logs.append(
                {
                    "change_id": str(uuid.uuid4()),
                    "entity_type": "capability",
                    "entity_id": child_capability.capability_id,
                    "action": "split",
                    "changed_at": now_iso(),
                    "from_version": "",
                    "to_version": child_capability.version,
                    "from_state": "",
                    "to_state": child_capability.status.value,
                    "summary": "split_from_existing_capability",
                    "related_entity_ids": [parent_capability.capability_id],
                    "provenance": provenance,
                }
            )
        deprecated_parent = self.mark_deprecated(
            capability=parent_capability,
            skills=list(existing_skills_by_capability_id.get(parent_capability.capability_id, []) or []),
            reason="split_into_more_specific_capabilities",
            state=VersionState.DEPRECATED,
            related_ids=[child.capability_id for child in updated_children],
        )
        return {
            "children": updated_children,
            "child_skills": updated_child_skills,
            "deprecated_parent": deprecated_parent,
            "lifecycles": lifecycles,
            "change_logs": change_logs,
            "version_history": version_history,
            "provenance_links": provenance_links,
        }

    def _change_payload(
        self,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        from_version: str,
        to_version: str,
        from_state: str,
        to_state: str,
        summary: str,
        provenance: Dict[str, Any],
        related_entity_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Builds one normalized change log payload."""

        return {
            "change_id": str(uuid.uuid4()),
            "entity_type": str(entity_type or "").strip(),
            "entity_id": str(entity_id or "").strip(),
            "action": str(action or "").strip(),
            "changed_at": now_iso(),
            "from_version": str(from_version or "").strip(),
            "to_version": str(to_version or "").strip(),
            "from_state": str(from_state or "").strip(),
            "to_state": str(to_state or "").strip(),
            "summary": str(summary or "").strip(),
            "related_entity_ids": list(related_entity_ids or []),
            "provenance": dict(provenance or {}),
        }

    def _history_payload(
        self,
        *,
        entity_type: str,
        entity_id: str,
        version: str,
        action: str,
        status: VersionState,
        related_entity_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Builds one normalized version history entry."""

        return {
            "entity_type": str(entity_type or "").strip(),
            "entity_id": str(entity_id or "").strip(),
            "version": str(version or "").strip(),
            "action": str(action or "").strip(),
            "changed_at": now_iso(),
            "status": status.value,
            "related_entity_ids": list(related_entity_ids or []),
        }

    def reconcile(
        self,
        *,
        capabilities: Sequence[CapabilitySpec],
        skill_specs: Sequence[SkillSpec],
        evidence_units: Sequence[EvidenceUnit],
        target_state: VersionState,
    ) -> VersionRegistrationResult:
        """Reconciles one compiled batch against registry state."""

        result = VersionRegistrationResult(
            evidence_units=list(evidence_units or []),
            dry_run=False,
        )
        evidence_by_id = _evidence_lookup(self.registry, evidence_units)
        existing_capabilities = list(self.registry.list_capabilities())
        existing_capabilities_by_id = {cap.capability_id: cap for cap in existing_capabilities}
        existing_skills_by_capability_id: Dict[str, List[SkillSpec]] = {}
        for skill in self.registry.list_skills():
            existing_skills_by_capability_id.setdefault(skill.capability_id, []).append(skill)

        incoming_skill_by_capability_id = {skill.capability_id: skill for skill in list(skill_specs or [])}
        decisions = [
            self.classify_change(
                capability,
                existing_capabilities=existing_capabilities,
                evidence_by_id=evidence_by_id,
            )
            for capability in list(capabilities or [])
        ]

        split_groups: Dict[str, List[ChangeDecision]] = {}
        for decision in decisions:
            if decision.action not in {"revise", "strengthen", "unchanged"}:
                continue
            parent_id = str(decision.split_parent_id or "")
            if not parent_id and list(decision.matched_capability_ids or []):
                parent_id = str(decision.matched_capability_ids[0] or "").strip()
            if not parent_id:
                continue
            split_groups.setdefault(parent_id, []).append(decision)

        for parent_id, bucket in split_groups.items():
            if len(bucket) < 2:
                continue
            pairwise_max = 0.0
            for idx, left in enumerate(bucket):
                for right in bucket[idx + 1 :]:
                    pairwise_max = max(
                        pairwise_max,
                        _list_similarity(left.capability.workflow_steps, right.capability.workflow_steps),
                    )
            if pairwise_max < 0.45:
                for item in bucket:
                    item.action = "split"
                    item.reason = "existing_capability_now_better_expressed_as_multiple_workflows"

        processed_split_parents: Set[str] = set()
        consumed_existing_ids: Set[str] = set()
        consumed_new_ids: Set[str] = set()

        for decision in [item for item in decisions if item.action == "merge"]:
            new_capability = decision.capability
            incoming_skill = incoming_skill_by_capability_id.get(new_capability.capability_id)
            if incoming_skill is None:
                result.errors.append({"capability_id": new_capability.capability_id, "error": "missing compiled skill for merge"})
                continue
            application = self.merge_skills(
                decision=decision,
                skill=incoming_skill,
                existing_capabilities_by_id=existing_capabilities_by_id,
                existing_skills_by_capability_id=existing_skills_by_capability_id,
                target_state=target_state,
            )
            merged_capability = application["primary_capability"]
            merged_skill = application["primary_skill"]
            consumed_new_ids.add(new_capability.capability_id)
            consumed_existing_ids.update(decision.matched_capability_ids)
            provenance = {
                "entity_type": "capability",
                "entity_id": merged_capability.capability_id,
                "doc_ids": _doc_ids_from_evidence(merged_capability.evidence_refs, evidence_by_id),
                "evidence_added": list(merged_capability.evidence_refs or []),
                "evidence_removed": [],
                "evidence_conflicts": _conflicting_evidence_ids(merged_capability.evidence_refs, evidence_by_id),
                "related_entity_ids": decision.matched_capability_ids,
            }
            result.capabilities.append(merged_capability)
            result.skill_specs.append(merged_skill)
            result.lifecycles.append(
                self.update_lifecycle(
                    skill_id=merged_skill.skill_id,
                    capability_id=merged_capability.capability_id,
                    current_state=_first_skill_for_capability(existing_skills_by_capability_id, merged_capability.capability_id).status if _first_skill_for_capability(existing_skills_by_capability_id, merged_capability.capability_id) is not None else None,
                    action="merge",
                    target_state=target_state,
                    metadata={"merged_from_capability_ids": decision.matched_capability_ids},
                )
            )
            result.provenance_links.append(provenance)
            result.change_logs.append(
                self._change_payload(
                    entity_type="capability",
                    entity_id=merged_capability.capability_id,
                    action="merge",
                    from_version=existing_capabilities_by_id[merged_capability.capability_id].version,
                    to_version=merged_capability.version,
                    from_state=existing_capabilities_by_id[merged_capability.capability_id].status.value,
                    to_state=merged_capability.status.value,
                    summary=decision.reason,
                    provenance=provenance,
                    related_entity_ids=decision.matched_capability_ids,
                )
            )
            result.version_history.append(
                self._history_payload(
                    entity_type="capability",
                    entity_id=merged_capability.capability_id,
                    version=merged_capability.version,
                    action="merge",
                    status=merged_capability.status,
                    related_entity_ids=decision.matched_capability_ids,
                )
            )
            result.version_history.append(
                self._history_payload(
                    entity_type="skill",
                    entity_id=merged_skill.skill_id,
                    version=merged_skill.version,
                    action="merge",
                    status=merged_skill.status,
                    related_entity_ids=decision.matched_capability_ids,
                )
            )
            for secondary in list(application["secondary"] or []):
                result.capabilities.append(secondary["capability"])
                result.skill_specs.extend(list(secondary["skills"] or []))
                result.lifecycles.extend(list(secondary["lifecycles"] or []))
                result.change_logs.extend(list(secondary["change_logs"] or []))
                result.version_history.extend(list(secondary["version_history"] or []))
                result.provenance_links.extend(list(secondary["provenance_links"] or []))
            emit_stage_log(self.logger, f"[register_versions] merge capability={merged_capability.capability_id} from={decision.matched_capability_ids}")

        for parent_id, bucket in split_groups.items():
            actionable = [item for item in bucket if item.action == "split"]
            if not actionable or parent_id in processed_split_parents:
                continue
            parent = existing_capabilities_by_id.get(parent_id)
            if parent is None:
                continue
            child_capabilities = [item.capability for item in actionable]
            child_skills = {}
            for child in child_capabilities:
                incoming_skill = incoming_skill_by_capability_id.get(child.capability_id)
                if incoming_skill is not None:
                    child_skills[child.capability_id] = incoming_skill
            if len(child_skills) != len(child_capabilities):
                result.errors.append({"capability_id": parent_id, "error": "missing compiled skills for split children"})
                continue
            application = self.split_skill(
                parent_capability=parent,
                child_capabilities=child_capabilities,
                child_skills_by_capability_id=child_skills,
                existing_skills_by_capability_id=existing_skills_by_capability_id,
                target_state=target_state,
            )
            processed_split_parents.add(parent_id)
            consumed_existing_ids.add(parent_id)
            for item in actionable:
                consumed_new_ids.add(item.capability.capability_id)
            result.capabilities.extend(list(application["children"] or []))
            result.skill_specs.extend(list(application["child_skills"] or []))
            result.lifecycles.extend(list(application["lifecycles"] or []))
            result.change_logs.extend(list(application["change_logs"] or []))
            result.version_history.extend(list(application["version_history"] or []))
            result.provenance_links.extend(list(application["provenance_links"] or []))
            result.capabilities.append(application["deprecated_parent"]["capability"])
            result.skill_specs.extend(list(application["deprecated_parent"]["skills"] or []))
            result.lifecycles.extend(list(application["deprecated_parent"]["lifecycles"] or []))
            result.change_logs.extend(list(application["deprecated_parent"]["change_logs"] or []))
            result.version_history.extend(list(application["deprecated_parent"]["version_history"] or []))
            result.provenance_links.extend(list(application["deprecated_parent"]["provenance_links"] or []))
            emit_stage_log(self.logger, f"[register_versions] split capability={parent_id} into={len(child_capabilities)}")

        for decision in decisions:
            if decision.capability.capability_id in consumed_new_ids:
                continue
            if decision.action not in {"create", "strengthen", "revise", "unchanged"}:
                continue

            new_capability = decision.capability
            incoming_skill = incoming_skill_by_capability_id.get(new_capability.capability_id)
            if incoming_skill is None:
                result.errors.append({"capability_id": new_capability.capability_id, "error": "missing compiled skill"})
                continue

            if decision.action == "create":
                updated_capability = _copy_capability(
                    new_capability,
                    version=self.create_new_version(current_version=new_capability.version, action="create"),
                    status=target_state,
                    metadata_update={"change_action": "create"},
                )
                updated_skill = _copy_skill(
                    incoming_skill,
                    version=updated_capability.version,
                    status=target_state,
                    metadata_update={"change_action": "create"},
                )
                provenance = {
                    "entity_type": "capability",
                    "entity_id": updated_capability.capability_id,
                    "doc_ids": _doc_ids_from_evidence(updated_capability.evidence_refs, evidence_by_id),
                    "evidence_added": list(updated_capability.evidence_refs or []),
                    "evidence_removed": [],
                    "evidence_conflicts": _conflicting_evidence_ids(updated_capability.evidence_refs, evidence_by_id),
                    "related_entity_ids": [],
                }
                result.capabilities.append(updated_capability)
                result.skill_specs.append(updated_skill)
                result.lifecycles.append(
                    self.update_lifecycle(
                        skill_id=updated_skill.skill_id,
                        capability_id=updated_capability.capability_id,
                        current_state=None,
                        action="create",
                        target_state=target_state,
                        metadata={"doc_ids": provenance["doc_ids"]},
                    )
                )
                result.change_logs.append(
                    self._change_payload(
                        entity_type="capability",
                        entity_id=updated_capability.capability_id,
                        action="create",
                        from_version="",
                        to_version=updated_capability.version,
                        from_state="",
                        to_state=updated_capability.status.value,
                        summary=decision.reason,
                        provenance=provenance,
                    )
                )
                result.version_history.append(
                    self._history_payload(
                        entity_type="capability",
                        entity_id=updated_capability.capability_id,
                        version=updated_capability.version,
                        action="create",
                        status=updated_capability.status,
                    )
                )
                result.version_history.append(
                    self._history_payload(
                        entity_type="skill",
                        entity_id=updated_skill.skill_id,
                        version=updated_skill.version,
                        action="create",
                        status=updated_skill.status,
                        related_entity_ids=[updated_capability.capability_id],
                    )
                )
                result.provenance_links.append(provenance)
                emit_stage_log(self.logger, f"[register_versions] create capability={updated_capability.capability_id}")
                continue

            existing_capability = existing_capabilities_by_id.get(decision.matched_capability_ids[0])
            if existing_capability is None:
                result.errors.append({"capability_id": new_capability.capability_id, "error": "matched capability missing from registry"})
                continue
            existing_skill = _first_skill_for_capability(existing_skills_by_capability_id, existing_capability.capability_id)
            current_version = existing_capability.version
            next_version = self.create_new_version(current_version=current_version, action=decision.action)
            if decision.action == "unchanged":
                next_version = current_version
            updated_capability = _copy_capability(
                new_capability,
                capability_id=existing_capability.capability_id,
                version=next_version,
                status=(existing_capability.status if decision.action == "unchanged" else target_state),
                metadata_update={
                    "change_action": decision.action,
                    "previous_capability_id": existing_capability.capability_id,
                },
            )
            updated_skill = _copy_skill(
                incoming_skill,
                skill_id=(existing_skill.skill_id if existing_skill is not None else _skill_id_for_capability(updated_capability.capability_id)),
                capability_id=updated_capability.capability_id,
                version=updated_capability.version,
                status=((existing_skill.status if existing_skill is not None else target_state) if decision.action == "unchanged" else target_state),
                metadata_update={
                    "change_action": decision.action,
                    "previous_capability_id": existing_capability.capability_id,
                },
            )
            best_diff = decision.diffs[0] if decision.diffs else self.diff_capability(updated_capability, existing_capability, evidence_by_id=evidence_by_id)
            provenance = {
                "entity_type": "capability",
                "entity_id": updated_capability.capability_id,
                "doc_ids": list(best_diff.doc_ids or []),
                "evidence_added": list(best_diff.evidence_added or []),
                "evidence_removed": list(best_diff.evidence_removed or []),
                "evidence_conflicts": list(best_diff.conflicting_evidence or []),
                "related_entity_ids": [existing_capability.capability_id],
            }
            result.capabilities.append(updated_capability)
            result.skill_specs.append(updated_skill)
            consumed_existing_ids.add(existing_capability.capability_id)
            if decision.action != "unchanged":
                result.lifecycles.append(
                    self.update_lifecycle(
                        skill_id=updated_skill.skill_id,
                        capability_id=updated_capability.capability_id,
                        current_state=(existing_skill.status if existing_skill is not None else existing_capability.status),
                        action=decision.action,
                        target_state=target_state,
                        metadata={
                            "doc_ids": provenance["doc_ids"],
                            "evidence_added": provenance["evidence_added"],
                            "evidence_removed": provenance["evidence_removed"],
                            "evidence_conflicts": provenance["evidence_conflicts"],
                        },
                    )
                )
                result.change_logs.append(
                    self._change_payload(
                        entity_type="capability",
                        entity_id=updated_capability.capability_id,
                        action=decision.action,
                        from_version=existing_capability.version,
                        to_version=updated_capability.version,
                        from_state=existing_capability.status.value,
                        to_state=updated_capability.status.value,
                        summary=decision.reason,
                        provenance=provenance,
                        related_entity_ids=[existing_capability.capability_id],
                    )
                )
                result.version_history.append(
                    self._history_payload(
                        entity_type="capability",
                        entity_id=updated_capability.capability_id,
                        version=updated_capability.version,
                        action=decision.action,
                        status=updated_capability.status,
                        related_entity_ids=[existing_capability.capability_id],
                    )
                )
                result.version_history.append(
                    self._history_payload(
                        entity_type="skill",
                        entity_id=updated_skill.skill_id,
                        version=updated_skill.version,
                        action=decision.action,
                        status=updated_skill.status,
                        related_entity_ids=[updated_capability.capability_id],
                    )
                )
                result.provenance_links.append(provenance)
                emit_stage_log(self.logger, f"[register_versions] {decision.action} capability={updated_capability.capability_id}")

        incoming_related = list(capabilities or [])
        for existing_capability in existing_capabilities:
            if existing_capability.capability_id in consumed_existing_ids:
                continue
            if existing_capability.status in {VersionState.DEPRECATED, VersionState.RETIRED}:
                continue
            related_diffs = [
                self.diff_capability(candidate, existing_capability, evidence_by_id=evidence_by_id)
                for candidate in incoming_related
                if (
                    candidate.domain == existing_capability.domain
                    or candidate.task_family == existing_capability.task_family
                    or candidate.method_family == existing_capability.method_family
                )
            ]
            if not related_diffs:
                continue
            strongest = sorted(related_diffs, key=lambda item: item.overall_similarity, reverse=True)[0]
            if strongest.overall_similarity < 0.35 or not strongest.conflicting_evidence:
                continue
            deprecated_state = VersionState.DEPRECATED if len(strongest.conflicting_evidence) >= 2 else VersionState.WATCHLIST
            deprecated = self.mark_deprecated(
                capability=existing_capability,
                skills=list(existing_skills_by_capability_id.get(existing_capability.capability_id, []) or []),
                reason="new_conflicting_evidence_no_longer_supports_old_capability",
                state=deprecated_state,
                related_ids=[strongest.candidate_capability_id],
            )
            result.capabilities.append(deprecated["capability"])
            result.skill_specs.extend(list(deprecated["skills"] or []))
            result.lifecycles.extend(list(deprecated["lifecycles"] or []))
            result.change_logs.extend(list(deprecated["change_logs"] or []))
            result.version_history.extend(list(deprecated["version_history"] or []))
            result.provenance_links.extend(list(deprecated["provenance_links"] or []))
            consumed_existing_ids.add(existing_capability.capability_id)
            emit_stage_log(self.logger, f"[register_versions] deprecate capability={existing_capability.capability_id}")

        return result


def register_versions(
    *,
    registry: DocumentRegistry,
    documents: Sequence[DocumentRecord],
    evidence_units: Sequence[EvidenceUnit],
    capabilities: Sequence[CapabilitySpec],
    skill_specs: Sequence[SkillSpec],
    sdk: Optional[AutoSkill] = None,
    user_id: str = "u1",
    metadata: Optional[Dict[str, Any]] = None,
    dry_run: bool = False,
    target_state: VersionState = VersionState.ACTIVE,
    logger: StageLogger = None,
) -> VersionRegistrationResult:
    """
    Registers a compiled batch into the document registry and optionally the skill store.

    Versioning policy:
    - capabilities are matched semantically, not only by capability_id
    - skill versions always follow capability versions
    - registry stores lifecycle, version history, change logs, and provenance links
    """

    effective_state = VersionState.DRAFT if dry_run else target_state
    manager = VersionManager(registry=registry, logger=logger)
    reconciled = manager.reconcile(
        capabilities=capabilities,
        skill_specs=skill_specs,
        evidence_units=evidence_units,
        target_state=effective_state,
    )
    reconciled.documents = list(documents or [])
    reconciled.evidence_units = list(evidence_units or [])
    reconciled.dry_run = bool(dry_run)

    if not dry_run:
        for document in documents or []:
            registry.upsert_document(document)
        for unit in evidence_units or []:
            registry.upsert_evidence(unit)
        seen_capabilities: Set[str] = set()
        for capability in reconciled.capabilities:
            if capability.capability_id in seen_capabilities:
                continue
            registry.upsert_capability(capability)
            seen_capabilities.add(capability.capability_id)
        seen_skills: Set[str] = set()
        for skill in reconciled.skill_specs:
            if skill.skill_id in seen_skills:
                continue
            registry.upsert_skill(skill)
            seen_skills.add(skill.skill_id)
        for lifecycle in reconciled.lifecycles:
            registry.append_lifecycle(lifecycle)
        for payload in reconciled.change_logs:
            registry.append_change_log(str(payload.get("change_id") or str(uuid.uuid4())), payload)
        for entry in reconciled.version_history:
            registry.append_version_history(
                entity_type=str(entry.get("entity_type") or ""),
                entity_id=str(entry.get("entity_id") or ""),
                entry=entry,
            )
        for payload in reconciled.provenance_links:
            registry.upsert_provenance_links(
                entity_type=str(payload.get("entity_type") or ""),
                entity_id=str(payload.get("entity_id") or ""),
                payload=payload,
            )

    if sdk is not None and reconciled.skill_specs:
        candidates = [
            skill_spec_to_candidate(spec)
            for spec in reconciled.skill_specs
            if spec.status in _ACTIVE_STORE_STATES
        ]
        md = dict(metadata or {})
        md.setdefault("channel", "offline_extract_from_doc")
        md.setdefault("source_type", "document")
        md["document_registry_root"] = registry.root_dir
        if candidates:
            if not dry_run:
                try:
                    with activate_offline_prompt_runtime(sdk=sdk, channel="offline_extract_from_doc"):
                        updated = sdk.maintainer.apply(
                            candidates,
                            user_id=str(user_id or "").strip() or "u1",
                            metadata=md,
                        )
                    reconciled.upserted_store_skills = [_plain_skill(skill) for skill in (updated or [])]
                    emit_stage_log(logger, f"[register_versions] store_upserts={len(reconciled.upserted_store_skills)}")
                except Exception as e:
                    reconciled.errors.append({"stage": "store_upsert", "error": str(e)})
                    emit_stage_log(logger, f"[register_versions] store upsert error: {e}")
            else:
                emit_stage_log(logger, f"[register_versions] dry-run store_upserts={len(candidates)}")

    return reconciled
