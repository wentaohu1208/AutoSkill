"""
Staged offline document pipeline orchestration.

The pipeline is intentionally organized as explicit stages so callers can rerun
or override any stage independently:
- ingest_document
- extract_evidence
- induce_capabilities
- compile_skills
- register_versions
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from autoskill import AutoSkill

from .common import StageLogger
from .compiler import (
    SkillCompilationResult,
    SkillCompiler,
    build_skill_compiler,
    compile_skills,
)
from .extractor import (
    EvidenceExtractionResult,
    EvidenceExtractor,
    build_evidence_extractor,
    extract_evidence,
)
from .inducer import (
    CapabilityInducer,
    CapabilityInductionResult,
    build_capability_inducer,
    induce_capabilities,
)
from .ingest import (
    DocumentIngestResult,
    DocumentIngestor,
    HeuristicDocumentIngestor,
    ingest_document,
)
from .registry import DocumentRegistry, build_registry_from_store_config
from .versioning import VersionRegistrationResult, register_versions
from .models import CapabilitySpec, DocumentRecord, EvidenceUnit, SkillSpec, VersionState


@dataclass
class DocumentBuildResult:
    """Top-level result of a full offline document build run."""

    ingest: DocumentIngestResult
    evidence: EvidenceExtractionResult
    capabilities: CapabilityInductionResult
    skills: SkillCompilationResult
    registration: VersionRegistrationResult
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Returns a compact build summary suitable for CLI/API output."""

        return {
            "dry_run": bool(self.dry_run),
            "documents": len(self.ingest.documents),
            "skipped_documents": len(self.ingest.skipped_documents),
            "evidence_units": len(self.evidence.evidence_units),
            "capabilities": len(self.capabilities.capabilities),
            "skill_specs": len(self.skills.skill_specs),
            "lifecycles": len(self.registration.lifecycles),
            "change_logs": len(self.registration.change_logs),
            "version_history_entries": len(self.registration.version_history),
            "provenance_links": len(self.registration.provenance_links),
            "store_upserts": len(self.registration.upserted_store_skills),
            "errors": (
                list(self.ingest.errors)
                + list(self.evidence.errors)
                + list(self.capabilities.errors)
                + list(self.skills.errors)
                + list(self.registration.errors)
            ),
        }


class DocumentBuildPipeline:
    """Composable staged pipeline for offline document compilation."""

    def __init__(
        self,
        *,
        registry: DocumentRegistry,
        sdk: Optional[AutoSkill] = None,
        document_ingestor: Optional[DocumentIngestor] = None,
        evidence_extractor: Optional[EvidenceExtractor] = None,
        capability_inducer: Optional[CapabilityInducer] = None,
        skill_compiler: Optional[SkillCompiler] = None,
        logger: StageLogger = None,
    ) -> None:
        """Builds a pipeline with replaceable stage implementations."""

        self.registry = registry
        self.sdk = sdk
        self.document_ingestor = document_ingestor or HeuristicDocumentIngestor()
        self.evidence_extractor = evidence_extractor or build_evidence_extractor("heuristic")
        self.capability_inducer = capability_inducer or build_capability_inducer("heuristic")
        self.skill_compiler = skill_compiler or build_skill_compiler("heuristic")
        self.logger = logger

    def ingest_document(
        self,
        *,
        data: Optional[Any] = None,
        file_path: str = "",
        title: str = "",
        source_type: str = "document",
        domain: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        continue_on_error: bool = True,
        dry_run: bool = False,
    ) -> DocumentIngestResult:
        """Runs the ingestion stage only."""

        return ingest_document(
            data=data,
            file_path=file_path,
            title=title,
            source_type=source_type,
            domain=domain,
            metadata=metadata,
            registry=self.registry,
            ingestor=self.document_ingestor,
            continue_on_error=continue_on_error,
            dry_run=dry_run,
            logger=self.logger,
        )

    def extract_evidence(
        self,
        *,
        documents: List[DocumentRecord],
    ) -> EvidenceExtractionResult:
        """Runs the evidence extraction stage only."""

        return extract_evidence(
            documents=list(documents or []),
            extractor=self.evidence_extractor,
            logger=self.logger,
        )

    def induce_capabilities(
        self,
        *,
        documents: List[DocumentRecord],
        evidence_units: List[EvidenceUnit],
    ) -> CapabilityInductionResult:
        """Runs the capability induction stage only."""

        return induce_capabilities(
            documents=list(documents or []),
            evidence_units=list(evidence_units or []),
            inducer=self.capability_inducer,
            logger=self.logger,
        )

    def compile_skills(
        self,
        *,
        capabilities: List[CapabilitySpec],
        target_state: VersionState = VersionState.DRAFT,
    ) -> SkillCompilationResult:
        """Runs the skill compilation stage only."""

        return compile_skills(
            capabilities=list(capabilities or []),
            compiler=self.skill_compiler,
            target_state=target_state,
            logger=self.logger,
        )

    def register_versions(
        self,
        *,
        documents: List[DocumentRecord],
        evidence_units: List[EvidenceUnit],
        capabilities: List[CapabilitySpec],
        skill_specs: List[SkillSpec],
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
        target_state: VersionState = VersionState.ACTIVE,
    ) -> VersionRegistrationResult:
        """Runs the registry/version registration stage only."""

        return register_versions(
            registry=self.registry,
            documents=list(documents or []),
            evidence_units=list(evidence_units or []),
            capabilities=list(capabilities or []),
            skill_specs=list(skill_specs or []),
            sdk=self.sdk,
            user_id=str(user_id or "").strip() or "u1",
            metadata=metadata,
            dry_run=dry_run,
            target_state=target_state,
            logger=self.logger,
        )

    def build(
        self,
        *,
        user_id: str,
        data: Optional[Any] = None,
        file_path: str = "",
        title: str = "",
        source_type: str = "document",
        domain: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        continue_on_error: bool = True,
        dry_run: bool = False,
        target_state: Optional[VersionState] = None,
    ) -> DocumentBuildResult:
        """Runs the full offline document build pipeline."""

        effective_state = target_state or (VersionState.DRAFT if dry_run else VersionState.ACTIVE)
        ingest_result = self.ingest_document(
            data=data,
            file_path=file_path,
            title=title,
            source_type=source_type,
            domain=domain,
            metadata=metadata,
            continue_on_error=continue_on_error,
            dry_run=dry_run,
        )
        evidence_result = self.extract_evidence(documents=ingest_result.documents)
        capability_result = self.induce_capabilities(
            documents=ingest_result.documents,
            evidence_units=evidence_result.evidence_units,
        )
        skill_result = self.compile_skills(
            capabilities=capability_result.capabilities,
            target_state=effective_state,
        )
        registration_result = self.register_versions(
            documents=ingest_result.documents,
            evidence_units=capability_result.evidence_units,
            capabilities=capability_result.capabilities,
            skill_specs=skill_result.skill_specs,
            user_id=user_id,
            metadata=metadata,
            dry_run=dry_run,
            target_state=effective_state,
        )
        return DocumentBuildResult(
            ingest=ingest_result,
            evidence=evidence_result,
            capabilities=capability_result,
            skills=skill_result,
            registration=registration_result,
            dry_run=bool(dry_run),
        )


def build_default_document_pipeline(
    *,
    sdk: Optional[AutoSkill] = None,
    registry_root: str = "",
    logger: StageLogger = None,
) -> DocumentBuildPipeline:
    """Builds the default staged document pipeline."""

    if registry_root:
        registry = DocumentRegistry(root_dir=registry_root)
    elif sdk is not None:
        registry = build_registry_from_store_config(dict(getattr(getattr(sdk, "config", None), "store", {}) or {}))
    else:
        from .registry import default_registry_root

        registry = DocumentRegistry(root_dir=default_registry_root("SkillBank"))
    return DocumentBuildPipeline(registry=registry, sdk=sdk, logger=logger)
