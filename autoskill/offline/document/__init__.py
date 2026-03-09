"""Offline document pipeline exports."""

from __future__ import annotations

from typing import Any

__all__ = [
    "extract_from_doc",
    "main",
    "DocumentBuildPipeline",
    "DocumentBuildResult",
    "build_default_document_pipeline",
    "ingest_document",
    "extract_evidence",
    "induce_capabilities",
    "compile_skills",
    "register_versions",
    "VersionManager",
    "DocumentRecord",
    "DocumentSection",
    "EvidenceUnit",
    "CapabilitySpec",
    "SkillSpec",
    "SkillLifecycle",
    "VersionState",
    "TextSpan",
    "ProvenanceRecord",
    "DocumentRegistry",
    "build_registry_from_store_config",
    "default_registry_root",
]


def __getattr__(name: str) -> Any:
    """Lazily resolves offline document pipeline exports."""
    if name == "extract_from_doc":
        from .extract import extract_from_doc as fn

        return fn
    if name == "main":
        from .extract import main as fn

        return fn
    if name in {
        "DocumentBuildPipeline",
        "DocumentBuildResult",
        "build_default_document_pipeline",
    }:
        from .pipeline import (
            DocumentBuildPipeline,
            DocumentBuildResult,
            build_default_document_pipeline,
        )

        mapping = {
            "DocumentBuildPipeline": DocumentBuildPipeline,
            "DocumentBuildResult": DocumentBuildResult,
            "build_default_document_pipeline": build_default_document_pipeline,
        }
        return mapping[name]
    if name in {
        "ingest_document",
        "extract_evidence",
        "induce_capabilities",
        "compile_skills",
        "register_versions",
        "VersionManager",
    }:
        from .compiler import compile_skills
        from .extractor import extract_evidence
        from .inducer import induce_capabilities
        from .ingest import ingest_document
        from .versioning import VersionManager, register_versions

        mapping = {
            "ingest_document": ingest_document,
            "extract_evidence": extract_evidence,
            "induce_capabilities": induce_capabilities,
            "compile_skills": compile_skills,
            "register_versions": register_versions,
            "VersionManager": VersionManager,
        }
        return mapping[name]
    if name in {
        "DocumentRecord",
        "DocumentSection",
        "EvidenceUnit",
        "CapabilitySpec",
        "SkillSpec",
        "SkillLifecycle",
        "VersionState",
        "TextSpan",
        "ProvenanceRecord",
    }:
        from .models import (
            CapabilitySpec,
            DocumentRecord,
            DocumentSection,
            EvidenceUnit,
            ProvenanceRecord,
            SkillLifecycle,
            SkillSpec,
            TextSpan,
            VersionState,
        )

        mapping = {
            "DocumentRecord": DocumentRecord,
            "DocumentSection": DocumentSection,
            "EvidenceUnit": EvidenceUnit,
            "CapabilitySpec": CapabilitySpec,
            "SkillSpec": SkillSpec,
            "SkillLifecycle": SkillLifecycle,
            "VersionState": VersionState,
            "TextSpan": TextSpan,
            "ProvenanceRecord": ProvenanceRecord,
        }
        return mapping[name]
    if name in {"DocumentRegistry", "build_registry_from_store_config", "default_registry_root"}:
        from .registry import (
            DocumentRegistry,
            build_registry_from_store_config,
            default_registry_root,
        )

        mapping = {
            "DocumentRegistry": DocumentRegistry,
            "build_registry_from_store_config": build_registry_from_store_config,
            "default_registry_root": default_registry_root,
        }
        return mapping[name]
    raise AttributeError(name)
