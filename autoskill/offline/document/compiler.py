"""
Skill compilation stage for the offline document pipeline.

This stage converts `CapabilitySpec` objects into execution-focused `SkillSpec`
records and helper `SkillCandidate` objects that can be merged into the
existing AutoSkill store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import uuid
from typing import Dict, List, Protocol

from .common import StageLogger, dedupe_strings, emit_stage_log
from autoskill.management.extraction import SkillCandidate

from .models import CapabilitySpec, SkillSpec, VersionState


def _slugify(text: str) -> str:
    """Builds a compact reusable skill name token."""

    src = str(text or "").strip().lower()
    src = src.replace("/", "-").replace("\\", "-")
    src = re.sub(r"\s+", "-", src)
    src = re.sub(r"[^\w-]+", "-", src)
    src = re.sub(r"-{2,}", "-", src).strip("-_")
    return src[:64] or "document-skill"


def _dedupe(items: List[str]) -> List[str]:
    """Deduplicates string values while preserving order."""

    return dedupe_strings(items, lower=True)


def _render_skill_body(capability: CapabilitySpec) -> str:
    """Renders a capability into an execution-focused skill body."""

    lines: List[str] = []
    lines.append("# Goal")
    lines.append(capability.title.strip())
    lines.append("")

    if capability.trigger_conditions:
        lines.append("# Trigger Conditions")
        for item in capability.trigger_conditions:
            lines.append(f"- {item}")
        lines.append("")

    if capability.inputs_required:
        lines.append("# Inputs Required")
        for item in capability.inputs_required:
            lines.append(f"- {item}")
        lines.append("")

    if capability.workflow_steps:
        lines.append("# Workflow")
        for idx, step in enumerate(capability.workflow_steps, start=1):
            lines.append(f"{idx}. {step}")
        lines.append("")

    if capability.decision_rules:
        lines.append("# Decision Rules")
        for item in capability.decision_rules:
            lines.append(f"- {item}")
        lines.append("")

    if capability.constraints:
        lines.append("# Constraints")
        for item in capability.constraints:
            lines.append(f"- {item}")
        lines.append("")

    if capability.failure_modes:
        lines.append("# Failure Modes")
        for item in capability.failure_modes:
            lines.append(f"- {item}")
        lines.append("")

    if capability.output_contract:
        lines.append("# Output Contract")
        for key, value in capability.output_contract.items():
            if isinstance(value, list):
                lines.append(f"- {key}:")
                for item in value:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"- {key}: {value}")
        lines.append("")

    return "\n".join(lines).strip()


def _build_description(capability: CapabilitySpec) -> str:
    """Builds a compact skill description from capability metadata."""

    parts = [capability.title.strip()]
    scope = " / ".join(
        [
            part
            for part in [capability.domain, capability.task_family, capability.method_family]
            if str(part or "").strip()
        ]
    )
    if scope:
        parts.append(f"Scope: {scope}.")
    if capability.stage:
        parts.append(f"Stage: {capability.stage}.")
    return " ".join(parts).strip()


@dataclass
class SkillCompilationResult:
    """Output of the skill compilation stage."""

    capabilities: List[CapabilitySpec] = field(default_factory=list)
    skill_specs: List[SkillSpec] = field(default_factory=list)
    candidates: List[SkillCandidate] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)
    compiler_name: str = "heuristic"


class SkillCompiler(Protocol):
    """Pluggable capability-to-skill compiler interface."""

    def compile(
        self,
        *,
        capabilities: List[CapabilitySpec],
        target_state: VersionState,
        logger: StageLogger,
    ) -> SkillCompilationResult:
        """Compiles capabilities into skills and helper store candidates."""


class HeuristicSkillCompiler:
    """Rule-based capability-to-skill compiler used by the MVP pipeline."""

    def compile(
        self,
        *,
        capabilities: List[CapabilitySpec],
        target_state: VersionState,
        logger: StageLogger,
    ) -> SkillCompilationResult:
        """Compiles skills from capabilities using deterministic formatting."""

        result = SkillCompilationResult(capabilities=list(capabilities or []), compiler_name="heuristic")
        for capability in capabilities or []:
            try:
                spec = self._compile_one(capability=capability, target_state=target_state)
                result.skill_specs.append(spec)
                result.candidates.append(skill_spec_to_candidate(spec))
                emit_stage_log(logger, f"[compile_skills] capability={capability.capability_id} skill={spec.skill_id}")
            except Exception as e:
                result.errors.append({"capability_id": capability.capability_id, "error": str(e)})
                emit_stage_log(logger, f"[compile_skills] error capability={capability.capability_id}: {e}")
        return result

    def _compile_one(self, *, capability: CapabilitySpec, target_state: VersionState) -> SkillSpec:
        """Compiles one capability into a SkillSpec."""

        name_base = capability.title.strip() or capability.task_family or capability.method_family or "document-skill"
        skill_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"autoskill-skill-spec:{capability.capability_id}"))
        compiled_tags = _dedupe(
            [
                capability.domain,
                capability.task_family,
                capability.method_family,
                capability.stage,
                capability.risk_class,
            ]
        )
        compiled_triggers = _dedupe(list(capability.trigger_conditions or []))[:5]
        metadata = {
            "domain": capability.domain,
            "task_family": capability.task_family,
            "method_family": capability.method_family,
            "stage": capability.stage,
            "risk_class": capability.risk_class,
            "output_contract": dict(capability.output_contract or {}),
            "compiled_tags": compiled_tags,
            "compiled_triggers": compiled_triggers,
            "evidence_ref_count": len(capability.evidence_refs or []),
        }
        return SkillSpec(
            skill_id=skill_id,
            capability_id=capability.capability_id,
            name=_slugify(name_base),
            description=_build_description(capability),
            skill_body=_render_skill_body(capability),
            references=list(capability.evidence_refs or []),
            metadata=metadata,
            version=capability.version,
            status=target_state,
        )


def skill_spec_to_candidate(spec: SkillSpec) -> SkillCandidate:
    """Converts one SkillSpec into the store-facing SkillCandidate format."""

    metadata = dict(spec.metadata or {})
    triggers = [str(x).strip() for x in list(metadata.get("compiled_triggers") or []) if str(x).strip()]
    tags = [str(x).strip() for x in list(metadata.get("compiled_tags") or []) if str(x).strip()]
    return SkillCandidate(
        name=str(spec.name or "").strip(),
        description=str(spec.description or "").strip(),
        instructions=str(spec.skill_body or "").strip(),
        triggers=triggers,
        tags=tags,
        examples=[],
        confidence=0.8,
        source={
            "source_type": "document_capability",
            "capability_id": spec.capability_id,
            "skill_spec_id": spec.skill_id,
            "references": list(spec.references or []),
            "version": spec.version,
            "status": spec.status.value,
        },
    )


def build_skill_compiler(kind: str = "heuristic") -> SkillCompiler:
    """Builds a concrete skill compiler implementation."""

    name = str(kind or "").strip().lower() or "heuristic"
    if name in {"heuristic", "stub", "rule-based", "rule_based"}:
        return HeuristicSkillCompiler()
    raise ValueError(f"unsupported skill compiler: {kind}")


def compile_skills(
    *,
    capabilities: List[CapabilitySpec],
    compiler: Optional[SkillCompiler] = None,
    target_state: VersionState = VersionState.DRAFT,
    logger: StageLogger = None,
) -> SkillCompilationResult:
    """Public functional wrapper for the skill compilation stage."""

    impl = compiler or HeuristicSkillCompiler()
    return impl.compile(
        capabilities=list(capabilities or []),
        target_state=target_state,
        logger=logger,
    )
