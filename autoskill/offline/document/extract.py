"""
Staged offline document pipeline entrypoints.

This module wires the document pipeline into the existing AutoSkill SDK style:
- `extract_from_doc(...)` remains the programmatic entrypoint
- `main()` exposes a small CLI with stage-oriented commands

Commands:
- `build`: full document -> evidence -> capability -> skill -> registry/store flow
- `ingest`: only normalize/import documents and run incremental checks
- `extract`: stop after EvidenceUnit extraction
- `induce`: stop after CapabilitySpec induction
- `compile`: stop after SkillSpec compilation without persisting registry/store updates
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

from autoskill import AutoSkill, AutoSkillConfig

from .common import StageLogger
from .models import CapabilitySpec, DocumentRecord, EvidenceUnit, SkillSpec, VersionState
from .pipeline import DocumentBuildPipeline, DocumentBuildResult, build_default_document_pipeline
from ..provider_config import (
    build_embeddings_config as _build_provider_embeddings_config,
    build_llm_config as _build_provider_llm_config,
    pick_default_provider as _pick_default_provider,
)

_DOCUMENT_CLI_EXAMPLES = (
    "Examples:\n"
    "  autoskill offline document build --file ./paper.md --dry-run\n"
    "  autoskill offline document ingest --file ./docs/\n"
    "  autoskill offline document compile --file ./manual.md --json"
)


def extract_from_doc(
    *,
    sdk: AutoSkill,
    user_id: str,
    data: Optional[Any] = None,
    file_path: str = "",
    title: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    hint: Optional[str] = None,
    continue_on_error: bool = True,
    max_chars_per_chunk: int = 6000,
    overlap_chars: int = 300,
    domain: str = "",
    source_type: str = "document",
    registry_root: str = "",
    dry_run: bool = False,
    target_state: Optional[VersionState] = None,
    logger: StageLogger = None,
) -> Dict[str, Any]:
    """
    Runs the staged offline document pipeline and returns a compact summary.

    `max_chars_per_chunk` and `overlap_chars` are accepted for backward
    compatibility with the previous chunk-based implementation. The staged
    pipeline keeps them unused for now because extraction operates on document
    sections/evidence blocks rather than SDK ingest chunks.
    """

    _ = max_chars_per_chunk
    _ = overlap_chars

    md = dict(metadata or {})
    md.setdefault("channel", "offline_extract_from_doc")
    md.setdefault("source_type", str(source_type or "").strip() or "document")
    if hint and str(hint).strip():
        md.setdefault("hint", str(hint).strip())

    pipeline = build_default_document_pipeline(
        sdk=sdk,
        registry_root=str(registry_root or "").strip(),
        logger=logger,
    )
    result = pipeline.build(
        user_id=str(user_id or "").strip() or "u1",
        data=data,
        file_path=str(file_path or "").strip(),
        title=str(title or "").strip(),
        source_type=str(source_type or "").strip() or "document",
        domain=str(domain or "").strip(),
        metadata=md,
        continue_on_error=bool(continue_on_error),
        dry_run=bool(dry_run),
        target_state=target_state,
    )
    return _build_summary(pipeline=pipeline, result=result)


def _plain_skill_spec(spec: SkillSpec) -> Dict[str, Any]:
    """Serializes one SkillSpec into a compact CLI/API summary."""

    return {
        "skill_id": spec.skill_id,
        "capability_id": spec.capability_id,
        "name": spec.name,
        "description": spec.description,
        "version": spec.version,
        "status": spec.status.value,
        "references": list(spec.references or []),
    }


def _plain_document(record: DocumentRecord) -> Dict[str, Any]:
    """Serializes one DocumentRecord into a compact summary."""

    return {
        "doc_id": record.doc_id,
        "title": record.title,
        "source_type": record.source_type,
        "domain": record.domain,
        "content_hash": record.content_hash,
        "section_count": len(record.sections or []),
    }


def _plain_evidence(unit: EvidenceUnit) -> Dict[str, Any]:
    """Serializes one EvidenceUnit into a compact summary."""

    return {
        "evidence_id": unit.evidence_id,
        "doc_id": unit.doc_id,
        "claim_type": unit.claim_type,
        "section": unit.section,
        "task_family": unit.task_family,
        "method_family": unit.method_family,
        "confidence": unit.confidence,
        "normalized_claim": unit.normalized_claim,
    }


def _plain_capability(spec: CapabilitySpec) -> Dict[str, Any]:
    """Serializes one CapabilitySpec into a compact summary."""

    return {
        "capability_id": spec.capability_id,
        "title": spec.title,
        "domain": spec.domain,
        "task_family": spec.task_family,
        "method_family": spec.method_family,
        "stage": spec.stage,
        "risk_class": spec.risk_class,
        "version": spec.version,
        "evidence_refs": list(spec.evidence_refs or []),
    }


def _build_summary(*, pipeline: DocumentBuildPipeline, result: DocumentBuildResult) -> Dict[str, Any]:
    """Builds a stable plain-dict response from a DocumentBuildResult."""

    skills_out: List[Dict[str, Any]]
    if result.registration.upserted_store_skills:
        skills_out = list(result.registration.upserted_store_skills)
    else:
        skills_out = [_plain_skill_spec(spec) for spec in list(result.registration.skill_specs or [])]

    errors = (
        list(result.ingest.errors)
        + list(result.evidence.errors)
        + list(result.capabilities.errors)
        + list(result.skills.errors)
        + list(result.registration.errors)
    )
    total_units = len(result.ingest.documents) + len(result.ingest.skipped_documents)
    return {
        "dry_run": bool(result.dry_run),
        "registry_root": pipeline.registry.root_dir,
        "source_file": result.ingest.source_file,
        "total_units": total_units,
        "total_documents": len(result.ingest.documents),
        "skipped_documents": len(result.ingest.skipped_documents),
        "total_evidence_units": len(result.evidence.evidence_units),
        "total_capabilities": len(result.capabilities.capabilities),
        "total_skill_specs": len(result.skills.skill_specs),
        "lifecycle_events": len(result.registration.lifecycles),
        "change_events": len(result.registration.change_logs),
        "version_history_entries": len(result.registration.version_history),
        "provenance_links": len(result.registration.provenance_links),
        "upserted_count": len(result.registration.upserted_store_skills),
        "skills": skills_out,
        "errors": errors,
    }


def _env(name: str, default: str = "") -> str:
    """Reads one env var with empty-string fallback semantics."""

    val = os.getenv(name)
    return val if val is not None and val.strip() else default


def _build_llm_config(args: argparse.Namespace) -> Dict[str, Any]:
    """Builds the LLM provider config from CLI args."""

    provider = str(args.llm_provider or "mock").strip() or "mock"
    model = str(args.llm_model or "").strip() or None
    cfg = _build_provider_llm_config(provider, model=model)
    if str(args.llm_base_url or "").strip():
        cfg["base_url"] = str(args.llm_base_url).strip()
    if str(args.llm_api_key or "").strip():
        cfg["api_key"] = str(args.llm_api_key).strip()
    if str(args.auth_mode or "").strip():
        cfg["auth_mode"] = str(args.auth_mode).strip()
    return cfg


def _build_embeddings_config(args: argparse.Namespace) -> Dict[str, Any]:
    """Builds the embeddings provider config from CLI args."""

    llm_provider = str(args.llm_provider or "mock").strip().lower() or "mock"
    provider = str(args.embeddings_provider or "").strip()
    model = str(args.embeddings_model or "").strip() or None
    cfg = _build_provider_embeddings_config(provider, model=model, llm_provider=llm_provider)
    if str(args.embeddings_base_url or "").strip():
        cfg["base_url"] = str(args.embeddings_base_url).strip()
    if str(args.embeddings_api_key or "").strip():
        cfg["api_key"] = str(args.embeddings_api_key).strip()
    if str(args.embeddings_auth_mode or "").strip():
        cfg["auth_mode"] = str(args.embeddings_auth_mode).strip()
    dims = int(args.embeddings_dims or 0)
    provider_norm = str(cfg.get("provider") or "").strip().lower()
    if provider_norm == "hashing":
        cfg["dims"] = int(dims) if dims > 0 else 256
    elif dims > 0 and provider_norm != "none":
        cfg["dimensions"] = int(dims)
        cfg["extra_body"] = {"dimensions": int(dims)}
    return cfg


def _build_sdk_from_args(args: argparse.Namespace) -> AutoSkill:
    """Builds an AutoSkill SDK for document pipeline commands."""

    llm_cfg = _build_llm_config(args)
    emb_cfg = _build_embeddings_config(args)
    store_cfg: Dict[str, Any] = {"provider": "local"}
    if str(args.store_path or "").strip():
        store_cfg["path"] = str(args.store_path).strip()
    return AutoSkill(
        AutoSkillConfig(
            llm=llm_cfg,
            embeddings=emb_cfg,
            store=store_cfg,
            maintenance_strategy="heuristic" if str(args.maintenance_strategy or "").strip() == "heuristic" else "llm",
        )
    )


def _coerce_state(value: str, *, default: VersionState) -> VersionState:
    """Parses a CLI lifecycle state into VersionState."""

    raw = str(value or "").strip().lower()
    if not raw:
        return default
    return VersionState(raw)


def _build_logger(*, quiet: bool) -> StageLogger:
    """Builds a simple stdout logger for stage progress lines."""

    if quiet:
        return None

    def _emit(message: str) -> None:
        print(str(message), flush=True)

    return _emit


def _build_pipeline_from_args(args: argparse.Namespace) -> DocumentBuildPipeline:
    """Builds the default document pipeline from CLI args."""

    sdk = _build_sdk_from_args(args)
    return build_default_document_pipeline(
        sdk=sdk,
        registry_root=str(args.registry_root or "").strip(),
        logger=_build_logger(quiet=bool(args.quiet)),
    )


def _base_metadata(args: argparse.Namespace) -> Dict[str, Any]:
    """Builds shared metadata for CLI-triggered pipeline runs."""

    md = {"channel": "offline_extract_from_doc", "source_type": str(args.source_type or "").strip() or "document"}
    if str(args.hint or "").strip():
        md["hint"] = str(args.hint).strip()
    return md


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Registers shared CLI arguments for all document pipeline commands."""

    parser.add_argument("--file", required=True, help="Path to a document file or directory.")
    parser.add_argument("--user-id", default="u1", help="Target user id.")
    parser.add_argument("--title", default="", help="Optional document title override.")
    parser.add_argument("--domain", default="", help="Optional domain hint, e.g. chemistry or geography.")
    parser.add_argument("--source-type", default="document", help="Generic source type label.")
    parser.add_argument("--hint", default="", help="Optional extraction hint passed through metadata.")
    parser.add_argument("--dry-run", action="store_true", help="Run versioning without persisting registry or store changes.")
    parser.add_argument(
        "--registry-root",
        default=_env("AUTOSKILL_DOCUMENT_REGISTRY_ROOT", ""),
        help="Override the document registry root. Default: <store>/.autoskill/document_registry.",
    )
    parser.add_argument("--quiet", action="store_true", help="Disable stage log output.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of text summary.")
    parser.add_argument("--max-chars-per-chunk", type=int, default=6000, help=argparse.SUPPRESS)
    parser.add_argument("--overlap-chars", type=int, default=300, help=argparse.SUPPRESS)
    parser.add_argument(
        "--maintenance-strategy",
        default="heuristic",
        choices=["heuristic", "llm"],
        help="Skill store maintenance strategy used when build persists compiled skills.",
    )
    parser.add_argument(
        "--llm-provider",
        default=_env("AUTOSKILL_LLM_PROVIDER", _pick_default_provider()),
        help="mock|generic|glm|internlm|dashscope|openai|anthropic",
    )
    parser.add_argument("--llm-model", default=_env("AUTOSKILL_LLM_MODEL", ""), help="Optional LLM model id.")
    parser.add_argument("--llm-base-url", default=_env("AUTOSKILL_LLM_BASE_URL", ""), help="Optional LLM base URL.")
    parser.add_argument("--llm-api-key", default=_env("AUTOSKILL_LLM_API_KEY", ""), help="Optional LLM API key.")
    parser.add_argument("--auth-mode", default=_env("AUTOSKILL_LLM_AUTH_MODE", ""), help="Optional LLM auth mode.")
    parser.add_argument(
        "--embeddings-provider",
        default=_env("AUTOSKILL_EMBEDDINGS_PROVIDER", _env("AUTOSKILL_EMBEDDING_PROVIDER", "")),
        help="hashing|none|openai|generic|dashscope|glm",
    )
    parser.add_argument("--embeddings-model", default=_env("AUTOSKILL_EMBEDDINGS_MODEL", ""), help="Optional embeddings model id.")
    parser.add_argument("--embeddings-base-url", default=_env("AUTOSKILL_EMBEDDINGS_BASE_URL", ""), help="Optional embeddings base URL.")
    parser.add_argument("--embeddings-api-key", default=_env("AUTOSKILL_EMBEDDINGS_API_KEY", ""), help="Optional embeddings API key.")
    parser.add_argument("--embeddings-auth-mode", default=_env("AUTOSKILL_EMBEDDINGS_AUTH_MODE", ""), help="Optional embeddings auth mode.")
    parser.add_argument(
        "--embeddings-dims",
        type=int,
        default=int(_env("AUTOSKILL_EMBEDDINGS_DIMS", "0") or 0),
        help="Embedding dimension override (hashing uses dims; API providers use dimensions).",
    )
    parser.add_argument("--store-path", default=_env("AUTOSKILL_STORE_PATH", ""), help="Local SkillBank path used for compiled skill persistence.")


def build_parser() -> argparse.ArgumentParser:
    """Builds the staged document pipeline CLI parser."""

    parser_kwargs = {
        "formatter_class": argparse.RawDescriptionHelpFormatter,
    }
    parser = argparse.ArgumentParser(
        description="Run the staged offline AutoSkill document pipeline.",
        epilog=_DOCUMENT_CLI_EXAMPLES,
        **parser_kwargs,
    )
    subparsers = parser.add_subparsers(dest="command")

    build_parser = subparsers.add_parser(
        "build",
        help="Run the full document pipeline and persist registry/store updates.",
        description="Run all document pipeline stages and persist the resulting registry and skill updates.",
        epilog=_DOCUMENT_CLI_EXAMPLES,
        **parser_kwargs,
    )
    _add_common_args(build_parser)
    build_parser.add_argument(
        "--target-state",
        default=VersionState.ACTIVE.value,
        choices=[state.value for state in VersionState],
        help="Lifecycle state assigned to compiled skills when persisted.",
    )

    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Only ingest documents and run incremental checks.",
        description="Read documents, build DocumentRecord objects, and skip unchanged content.",
        **parser_kwargs,
    )
    _add_common_args(ingest_parser)

    extract_parser = subparsers.add_parser(
        "extract",
        help="Run ingest + evidence extraction without capability induction.",
        description="Read documents and extract EvidenceUnit records without inducing capabilities.",
        **parser_kwargs,
    )
    _add_common_args(extract_parser)

    induce_parser = subparsers.add_parser(
        "induce",
        help="Run ingest + extract + capability induction without compilation.",
        description="Read documents, extract evidence, and induce CapabilitySpec objects.",
        **parser_kwargs,
    )
    _add_common_args(induce_parser)

    compile_parser = subparsers.add_parser(
        "compile",
        help="Compile documents into SkillSpec output without registry/store persistence.",
        description="Run ingest, evidence extraction, capability induction, and SkillSpec compilation.",
        epilog=_DOCUMENT_CLI_EXAMPLES,
        **parser_kwargs,
    )
    _add_common_args(compile_parser)
    compile_parser.add_argument(
        "--target-state",
        default=VersionState.DRAFT.value,
        choices=[state.value for state in VersionState],
        help="Lifecycle state stamped on compiled SkillSpec output.",
    )
    return parser


def _print_errors(errors: List[Dict[str, Any]]) -> None:
    """Prints a compact error list for CLI commands."""

    if not errors:
        return
    print("Errors:")
    for item in errors[:20]:
        print(f"- {item}")


def _print_json(payload: Dict[str, Any]) -> None:
    """Prints one JSON payload with stable formatting."""

    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False))


def _run_build(args: argparse.Namespace) -> None:
    """Runs the full build command."""

    sdk = _build_sdk_from_args(args)
    result = extract_from_doc(
        sdk=sdk,
        user_id=str(args.user_id or "").strip() or "u1",
        file_path=str(args.file or "").strip(),
        title=str(args.title or "").strip(),
        domain=str(args.domain or "").strip(),
        source_type=str(args.source_type or "").strip() or "document",
        metadata=_base_metadata(args),
        hint=(str(args.hint).strip() or None),
        continue_on_error=True,
        max_chars_per_chunk=int(args.max_chars_per_chunk or 6000),
        overlap_chars=int(args.overlap_chars or 0),
        registry_root=str(args.registry_root or "").strip(),
        dry_run=bool(args.dry_run),
        target_state=_coerce_state(str(args.target_state or ""), default=VersionState.ACTIVE),
        logger=_build_logger(quiet=bool(args.quiet)),
    )
    if bool(args.json):
        _print_json(result)
        return
    print("Offline document build completed.")
    print(
        f"documents={result.get('total_documents', 0)} "
        f"skipped={result.get('skipped_documents', 0)} "
        f"evidence={result.get('total_evidence_units', 0)} "
        f"capabilities={result.get('total_capabilities', 0)} "
        f"skills={result.get('total_skill_specs', 0)} "
        f"lifecycles={result.get('lifecycle_events', 0)} "
        f"changes={result.get('change_events', 0)} "
        f"upserted={result.get('upserted_count', 0)}"
    )
    for idx, skill in enumerate(list(result.get("skills") or [])[:20], start=1):
        name = str(skill.get("name") or "").strip()
        version = str(skill.get("version") or "").strip()
        print(f"{idx}. {name} ({version})")
    _print_errors(list(result.get("errors") or []))


def _run_ingest(args: argparse.Namespace) -> None:
    """Runs only the ingest stage."""

    pipeline = _build_pipeline_from_args(args)
    result = pipeline.ingest_document(
        file_path=str(args.file or "").strip(),
        title=str(args.title or "").strip(),
        source_type=str(args.source_type or "").strip() or "document",
        domain=str(args.domain or "").strip(),
        metadata=_base_metadata(args),
        continue_on_error=True,
        dry_run=bool(args.dry_run),
    )
    payload = {
        "documents": [_plain_document(doc) for doc in list(result.documents or [])],
        "skipped_documents": [_plain_document(doc) for doc in list(result.skipped_documents or [])],
        "errors": list(result.errors or []),
    }
    if bool(args.json):
        _print_json(payload)
        return
    print("Offline document ingest completed.")
    print(
        f"documents={len(result.documents)} "
        f"skipped={len(result.skipped_documents)} "
        f"errors={len(result.errors)}"
    )
    for doc in list(result.documents or [])[:20]:
        print(f"- prepared: {doc.title} ({doc.doc_id})")
    for doc in list(result.skipped_documents or [])[:20]:
        print(f"- skipped: {doc.title} ({doc.doc_id})")
    _print_errors(list(result.errors or []))


def _run_extract(args: argparse.Namespace) -> None:
    """Runs ingest -> extract without capability induction or persistence."""

    pipeline = _build_pipeline_from_args(args)
    ingest_result = pipeline.ingest_document(
        file_path=str(args.file or "").strip(),
        title=str(args.title or "").strip(),
        source_type=str(args.source_type or "").strip() or "document",
        domain=str(args.domain or "").strip(),
        metadata=_base_metadata(args),
        continue_on_error=True,
        dry_run=bool(args.dry_run),
    )
    evidence_result = pipeline.extract_evidence(documents=ingest_result.documents)
    payload = {
        "documents": [_plain_document(doc) for doc in list(ingest_result.documents or [])],
        "skipped_documents": [_plain_document(doc) for doc in list(ingest_result.skipped_documents or [])],
        "evidence_units": [_plain_evidence(unit) for unit in list(evidence_result.evidence_units or [])],
        "errors": list(ingest_result.errors) + list(evidence_result.errors),
    }
    if bool(args.json):
        _print_json(payload)
        return
    print("Offline document extract completed.")
    print(
        f"documents={len(ingest_result.documents)} "
        f"skipped={len(ingest_result.skipped_documents)} "
        f"evidence={len(evidence_result.evidence_units)}"
    )
    for idx, unit in enumerate(list(evidence_result.evidence_units or [])[:20], start=1):
        print(f"{idx}. {unit.claim_type}: {unit.normalized_claim[:120]}")
    _print_errors(list(ingest_result.errors) + list(evidence_result.errors))


def _run_induce(args: argparse.Namespace) -> None:
    """Runs ingest -> extract -> induce without compilation or persistence."""

    pipeline = _build_pipeline_from_args(args)
    ingest_result = pipeline.ingest_document(
        file_path=str(args.file or "").strip(),
        title=str(args.title or "").strip(),
        source_type=str(args.source_type or "").strip() or "document",
        domain=str(args.domain or "").strip(),
        metadata=_base_metadata(args),
        continue_on_error=True,
        dry_run=bool(args.dry_run),
    )
    evidence_result = pipeline.extract_evidence(documents=ingest_result.documents)
    capability_result = pipeline.induce_capabilities(
        documents=ingest_result.documents,
        evidence_units=evidence_result.evidence_units,
    )
    payload = {
        "documents": [_plain_document(doc) for doc in list(ingest_result.documents or [])],
        "skipped_documents": [_plain_document(doc) for doc in list(ingest_result.skipped_documents or [])],
        "evidence_units": [_plain_evidence(unit) for unit in list(evidence_result.evidence_units or [])],
        "capabilities": [_plain_capability(spec) for spec in list(capability_result.capabilities or [])],
        "errors": list(ingest_result.errors) + list(evidence_result.errors) + list(capability_result.errors),
    }
    if bool(args.json):
        _print_json(payload)
        return
    print("Offline document induce completed.")
    print(
        f"documents={len(ingest_result.documents)} "
        f"skipped={len(ingest_result.skipped_documents)} "
        f"evidence={len(evidence_result.evidence_units)} "
        f"capabilities={len(capability_result.capabilities)}"
    )
    for idx, spec in enumerate(list(capability_result.capabilities or [])[:20], start=1):
        print(f"{idx}. {spec.title} ({spec.version})")
    _print_errors(
        list(ingest_result.errors)
        + list(evidence_result.errors)
        + list(capability_result.errors)
    )


def _run_compile(args: argparse.Namespace) -> None:
    """Runs ingest -> extract -> induce -> compile without persistence."""

    pipeline = _build_pipeline_from_args(args)
    ingest_result = pipeline.ingest_document(
        file_path=str(args.file or "").strip(),
        title=str(args.title or "").strip(),
        source_type=str(args.source_type or "").strip() or "document",
        domain=str(args.domain or "").strip(),
        metadata=_base_metadata(args),
        continue_on_error=True,
        dry_run=bool(args.dry_run),
    )
    evidence_result = pipeline.extract_evidence(documents=ingest_result.documents)
    capability_result = pipeline.induce_capabilities(
        documents=ingest_result.documents,
        evidence_units=evidence_result.evidence_units,
    )
    skill_result = pipeline.compile_skills(
        capabilities=capability_result.capabilities,
        target_state=_coerce_state(str(args.target_state or ""), default=VersionState.DRAFT),
    )
    payload = {
        "documents": [_plain_document(doc) for doc in list(ingest_result.documents or [])],
        "skipped_documents": [_plain_document(doc) for doc in list(ingest_result.skipped_documents or [])],
        "evidence_units": [_plain_evidence(unit) for unit in list(evidence_result.evidence_units or [])],
        "capabilities": [_plain_capability(spec) for spec in list(capability_result.capabilities or [])],
        "skills": [_plain_skill_spec(spec) for spec in list(skill_result.skill_specs or [])],
        "errors": list(ingest_result.errors)
        + list(evidence_result.errors)
        + list(capability_result.errors)
        + list(skill_result.errors),
    }
    if bool(args.json):
        _print_json(payload)
        return
    print("Offline document compile completed.")
    print(
        f"documents={len(ingest_result.documents)} "
        f"skipped={len(ingest_result.skipped_documents)} "
        f"evidence={len(evidence_result.evidence_units)} "
        f"capabilities={len(capability_result.capabilities)} "
        f"skills={len(skill_result.skill_specs)}"
    )
    for idx, spec in enumerate(list(skill_result.skill_specs or [])[:20], start=1):
        print(f"{idx}. {spec.name} ({spec.version}, {spec.status.value})")
    _print_errors(
        list(ingest_result.errors)
        + list(evidence_result.errors)
        + list(capability_result.errors)
        + list(skill_result.errors)
    )


def main(argv: Optional[Sequence[str]] = None) -> None:
    """CLI entrypoint for staged document pipeline commands."""

    raw_args = list(argv if argv is not None else sys.argv[1:])
    if not raw_args:
        build_parser().print_help()
        return
    if raw_args[0].startswith("-") and raw_args[0] not in {"-h", "--help"}:
        raw_args = ["build"] + raw_args

    args = build_parser().parse_args(raw_args)
    command = str(args.command or "build").strip() or "build"
    if command == "build":
        _run_build(args)
        return
    if command == "ingest":
        _run_ingest(args)
        return
    if command == "extract":
        _run_extract(args)
        return
    if command == "induce":
        _run_induce(args)
        return
    if command == "compile":
        _run_compile(args)
        return
    raise ValueError(f"unsupported command: {command}")


if __name__ == "__main__":
    main()
