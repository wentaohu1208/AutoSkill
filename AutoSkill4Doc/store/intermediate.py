"""
Intermediate run persistence for AutoSkill4Doc.

Long-running document extraction should expose observable artifacts before the
final registry/store sync completes. This module writes stage snapshots under
`<store_root>/.runtime/intermediate_runs/<run_id>/`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from autoskill.utils.time import now_iso

from ..models import DocumentRecord, SkillDraft, StrictWindow, SupportRecord
from .layout import intermediate_run_dir, normalize_library_root
from .staging import new_staging_run_id, safe_dir_component, safe_run_id

if TYPE_CHECKING:
    from ..ingest import DocumentIngestResult
    from ..stages.compiler import SkillCompilationResult
    from ..stages.extractor import SkillExtractionResult
    from ..store.versioning import VersionRegistrationResult


@dataclass
class IntermediateRunSummary:
    """Compact summary for one intermediate persistence run."""

    run_id: str
    run_dir: str
    status_path: str
    files: List[str] = field(default_factory=list)
    current_stage: str = "initialized"
    completed_stages: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Returns a JSON-safe summary payload."""

        return {
            "run_id": self.run_id,
            "run_dir": self.run_dir,
            "status_path": self.status_path,
            "files": list(self.files or []),
            "current_stage": self.current_stage,
            "completed_stages": list(self.completed_stages or []),
        }


def new_intermediate_run_id() -> str:
    """Creates a new run id for intermediate persistence."""

    return new_staging_run_id()


def build_resume_key(payload: Dict[str, Any]) -> str:
    """Builds a stable resume key for one pipeline invocation."""

    normalized = json.dumps(dict(payload or {}), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def find_intermediate_run_by_resume_key(*, base_store_root: str, resume_key: str) -> Optional[Dict[str, Any]]:
    """Returns the latest unfinished intermediate run that matches one resume key."""

    root = os.path.join(normalize_library_root(base_store_root), ".runtime", "intermediate_runs")
    key = str(resume_key or "").strip()
    if not key or not os.path.isdir(root):
        return None
    matches: List[Dict[str, Any]] = []
    for name in sorted(os.listdir(root)):
        status_path = os.path.join(root, name, "status.json")
        if not os.path.isfile(status_path):
            continue
        try:
            with open(status_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        metadata = dict(payload.get("metadata") or {})
        if str(metadata.get("resume_key") or "").strip() != key:
            continue
        if str(payload.get("status") or "").strip() == "completed":
            continue
        matches.append(payload)
    if not matches:
        return None
    matches.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""))
    return matches[-1]


class IntermediateRunWriter:
    """Writes incremental stage snapshots for one document build run."""

    def __init__(
        self,
        *,
        base_store_root: str,
        run_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        resume_existing: bool = False,
    ) -> None:
        store_root = normalize_library_root(base_store_root)
        resolved_run_id = safe_run_id(run_id or new_intermediate_run_id())
        self.run_id = resolved_run_id
        self.run_dir = intermediate_run_dir(base_store_root=store_root, run_id=resolved_run_id)
        self.status_path = os.path.join(self.run_dir, "status.json")
        self._files: List[str] = []
        if resume_existing and os.path.isfile(self.status_path):
            with open(self.status_path, "r", encoding="utf-8") as f:
                self._state = json.load(f)
            if not isinstance(self._state, dict):
                self._state = {}
            self._state["run_id"] = self.run_id
            self._state["run_dir"] = self.run_dir
            self._state["status"] = "running"
            self._state["updated_at"] = now_iso()
            self._files = self._discover_files()
            self._flush_state()
            return
        self._state: Dict[str, Any] = {
            "run_id": self.run_id,
            "run_dir": self.run_dir,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "status": "running",
            "current_stage": "initialized",
            "completed_stages": [],
            "metadata": dict(metadata or {}),
            "counts": {},
            "progress_counts": {
                "extract_support_records": 0,
                "extract_skill_drafts": 0,
                "processed_documents": 0,
            },
            "source_file": "",
        }
        os.makedirs(self.run_dir, exist_ok=True)
        self._flush_state()

    def _discover_files(self) -> List[str]:
        """Discovers persisted files already present under the run directory."""

        out: List[str] = []
        if not os.path.isdir(self.run_dir):
            return out
        for root, _, files in os.walk(self.run_dir):
            for name in sorted(files):
                path = os.path.join(root, name)
                if path == self.status_path:
                    continue
                out.append(path)
        return out

    def summary(self) -> IntermediateRunSummary:
        """Builds the latest run summary."""

        return IntermediateRunSummary(
            run_id=self.run_id,
            run_dir=self.run_dir,
            status_path=self.status_path,
            files=list(self._files or []),
            current_stage=str(self._state.get("current_stage") or "initialized"),
            completed_stages=list(self._state.get("completed_stages") or []),
        )

    def update_metadata(self, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Merges resolved run metadata into the persisted status payload."""

        if not isinstance(metadata, dict) or not metadata:
            return
        current = dict(self._state.get("metadata") or {})
        current.update(dict(metadata or {}))
        self._state["metadata"] = current
        self._state["updated_at"] = now_iso()
        self._flush_state()

    def write_ingest(self, result: "DocumentIngestResult") -> None:
        """Writes the completed ingest snapshot."""

        payload = {
            "source_file": result.source_file,
            "text_units": [unit.to_dict() for unit in list(result.text_units or [])],
            "documents": [doc.to_dict() for doc in list(result.documents or [])],
            "skipped_documents": [doc.to_dict() for doc in list(result.skipped_documents or [])],
            "windows": [window.to_dict() for window in list(result.windows or [])],
            "errors": list(result.errors or []),
        }
        self._write_json("ingest/result.json", payload)
        self._set_stage(
            stage="ingest_completed",
            completed_stage="ingest",
            source_file=result.source_file,
            counts={
                "documents": len(result.documents),
                "skipped_documents": len(result.skipped_documents),
                "text_units": len(result.text_units),
                "windows": len(result.windows),
            },
        )

    def write_extract_progress(
        self,
        *,
        record: DocumentRecord,
        supports: List[SupportRecord],
        drafts: List[SkillDraft],
        total_documents: int,
    ) -> None:
        """Writes per-document extraction progress as soon as one doc finishes."""

        progress = dict(self._state.get("progress_counts") or {})
        progress["extract_support_records"] = int(progress.get("extract_support_records") or 0) + len(list(supports or []))
        progress["extract_skill_drafts"] = int(progress.get("extract_skill_drafts") or 0) + len(list(drafts or []))
        progress["processed_documents"] = int(progress.get("processed_documents") or 0) + 1
        self._state["progress_counts"] = progress
        payload = {
            "doc_id": record.doc_id,
            "title": record.title,
            "source_file": str((record.metadata or {}).get("source_file") or ""),
            "supports": [support.to_dict() for support in list(supports or [])],
            "skill_drafts": [draft.to_dict() for draft in list(drafts or [])],
            "cumulative_support_records": int(progress.get("extract_support_records") or 0),
            "cumulative_skill_drafts": int(progress.get("extract_skill_drafts") or 0),
            "processed_documents": int(progress.get("processed_documents") or 0),
            "total_documents": int(total_documents or 0),
        }
        doc_name = safe_dir_component(str(record.doc_id or "").strip() or "document")
        self._write_json(f"extract/documents/{doc_name}.json", payload)
        self._set_stage(
            stage="extract_running",
            counts={
                "documents": total_documents,
                "processed_documents": min(total_documents, int(progress.get("processed_documents") or 0)),
                "support_records": int(progress.get("extract_support_records") or 0),
                "skill_drafts": int(progress.get("extract_skill_drafts") or 0),
            },
        )

    def write_extract(self, result: "SkillExtractionResult") -> None:
        """Writes the aggregate extraction snapshot."""

        payload = {
            "documents": [doc.to_dict() for doc in list(result.documents or [])],
            "windows": [window.to_dict() for window in list(result.windows or [])],
            "support_records": [support.to_dict() for support in list(result.support_records or [])],
            "skill_drafts": [draft.to_dict() for draft in list(result.skill_drafts or [])],
            "errors": list(result.errors or []),
        }
        self._write_json("extract/result.json", payload)
        self._set_stage(
            stage="extract_completed",
            completed_stage="extract",
            counts={
                "support_records": len(result.support_records),
                "skill_drafts": len(result.skill_drafts),
                "documents": len(result.documents),
                "windows": len(result.windows),
            },
        )

    def load_ingest(self) -> "DocumentIngestResult":
        """Loads the completed ingest snapshot."""

        from ..ingest import DocumentIngestResult
        from ..models import TextUnit

        path = os.path.join(self.run_dir, "ingest", "result.json")
        documents: List[DocumentRecord] = []
        skipped_documents: List[DocumentRecord] = []
        text_units: List[TextUnit] = []
        windows: List[StrictWindow] = []
        errors: List[Dict[str, Any]] = []
        source_file = str(self._state.get("source_file") or "").strip()
        if not os.path.isfile(path):
            return DocumentIngestResult(source_file=source_file, errors=[{"stage": "intermediate_ingest_load", "error": "ingest snapshot not found"}])
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                source_file = str(payload.get("source_file") or source_file).strip()
                documents = [DocumentRecord.from_dict(item) for item in list(payload.get("documents") or []) if isinstance(item, dict)]
                skipped_documents = [DocumentRecord.from_dict(item) for item in list(payload.get("skipped_documents") or []) if isinstance(item, dict)]
                text_units = [TextUnit.from_dict(item) for item in list(payload.get("text_units") or []) if isinstance(item, dict)]
                windows = [StrictWindow.from_dict(item) for item in list(payload.get("windows") or []) if isinstance(item, dict)]
                errors = [{"stage": "intermediate_ingest_load", **item} for item in list(payload.get("errors") or []) if isinstance(item, dict)]
        except Exception as exc:
            errors.append({"stage": "intermediate_ingest_load", "path": path, "error": str(exc)})
        return DocumentIngestResult(
            source_file=source_file,
            text_units=text_units,
            documents=documents,
            skipped_documents=skipped_documents,
            windows=windows,
            errors=errors,
        )

    def load_extract(self) -> "SkillExtractionResult":
        """Loads aggregated extraction results from per-document progress files."""

        from ..stages.extractor import SkillExtractionResult
        from ..models import DocumentRecord, StrictWindow

        extract_dir = os.path.join(self.run_dir, "extract", "documents")
        support_records: List[SupportRecord] = []
        skill_drafts: List[SkillDraft] = []
        errors: List[Dict[str, Any]] = []
        documents: List[DocumentRecord] = []
        windows: List[StrictWindow] = []
        aggregate_path = os.path.join(self.run_dir, "extract", "result.json")
        if os.path.isfile(aggregate_path):
            try:
                with open(aggregate_path, "r", encoding="utf-8") as f:
                    aggregate = json.load(f)
                if isinstance(aggregate, dict):
                    documents = [
                        DocumentRecord.from_dict(item)
                        for item in list(aggregate.get("documents") or [])
                        if isinstance(item, dict)
                    ]
                    windows = [
                        StrictWindow.from_dict(item)
                        for item in list(aggregate.get("windows") or [])
                        if isinstance(item, dict)
                    ]
                    errors.extend(
                        [{"stage": "intermediate_extract_result_load", **item} for item in list(aggregate.get("errors") or []) if isinstance(item, dict)]
                    )
            except Exception as exc:
                errors.append({"stage": "intermediate_extract_result_load", "path": aggregate_path, "error": str(exc)})
        if not documents or not windows:
            ingest_path = os.path.join(self.run_dir, "ingest", "result.json")
            if os.path.isfile(ingest_path):
                try:
                    with open(ingest_path, "r", encoding="utf-8") as f:
                        ingest_payload = json.load(f)
                    if isinstance(ingest_payload, dict):
                        if not documents:
                            documents = [
                                DocumentRecord.from_dict(item)
                                for item in list(ingest_payload.get("documents") or [])
                                if isinstance(item, dict)
                            ]
                        if not windows:
                            windows = [
                                StrictWindow.from_dict(item)
                                for item in list(ingest_payload.get("windows") or [])
                                if isinstance(item, dict)
                            ]
                except Exception as exc:
                    errors.append({"stage": "intermediate_ingest_result_load", "path": ingest_path, "error": str(exc)})
        if os.path.isdir(extract_dir):
            for name in sorted(os.listdir(extract_dir)):
                if not name.endswith(".json"):
                    continue
                path = os.path.join(extract_dir, name)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                except Exception as exc:
                    errors.append({"path": path, "error": str(exc)})
                    continue
                for item in list(payload.get("supports") or []):
                    if isinstance(item, dict):
                        support_records.append(SupportRecord.from_dict(item))
                for item in list(payload.get("skill_drafts") or []):
                    if isinstance(item, dict):
                        skill_drafts.append(SkillDraft.from_dict(item))
        seen_supports = {}
        for support in support_records:
            seen_supports[support.support_id] = support
        seen_drafts = {}
        for draft in skill_drafts:
            seen_drafts[draft.draft_id] = draft
        return SkillExtractionResult(
            documents=documents,
            windows=windows,
            support_records=list(seen_supports.values()),
            skill_drafts=list(seen_drafts.values()),
            errors=[{"stage": "intermediate_extract_load", **item} for item in errors],
            extractor_name="llm",
        )

    def processed_extract_doc_ids(self) -> List[str]:
        """Returns document ids that already have per-document extract snapshots."""

        extract_dir = os.path.join(self.run_dir, "extract", "documents")
        out: List[str] = []
        if not os.path.isdir(extract_dir):
            return out
        for name in sorted(os.listdir(extract_dir)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(extract_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception:
                continue
            doc_id = str((payload or {}).get("doc_id") or "").strip()
            if doc_id:
                out.append(doc_id)
        return out

    def write_compile(self, result: "SkillCompilationResult") -> None:
        """Writes the completed compile snapshot."""

        payload = {
            "support_records": [support.to_dict() for support in list(result.support_records or [])],
            "skill_drafts": [draft.to_dict() for draft in list(result.skill_drafts or [])],
            "skill_specs": [skill.to_dict() for skill in list(result.skill_specs or [])],
            "errors": list(result.errors or []),
        }
        self._write_json("compile/result.json", payload)
        self._set_stage(
            stage="compile_completed",
            completed_stage="compile",
            counts={
                "compiled_support_records": len(result.support_records),
                "compiled_skill_drafts": len(result.skill_drafts),
                "skill_specs": len(result.skill_specs),
            },
        )

    def load_compile(self) -> "SkillCompilationResult":
        """Loads the completed compile snapshot."""

        from ..models import SkillSpec
        from ..stages.compiler import SkillCompilationResult

        path = os.path.join(self.run_dir, "compile", "result.json")
        support_records: List[SupportRecord] = []
        skill_drafts: List[SkillDraft] = []
        skill_specs: List[SkillSpec] = []
        errors: List[Dict[str, Any]] = []
        if not os.path.isfile(path):
            return SkillCompilationResult(errors=[{"stage": "intermediate_compile_load", "error": "compile snapshot not found"}])
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                support_records = [SupportRecord.from_dict(item) for item in list(payload.get("support_records") or []) if isinstance(item, dict)]
                skill_drafts = [SkillDraft.from_dict(item) for item in list(payload.get("skill_drafts") or []) if isinstance(item, dict)]
                skill_specs = [SkillSpec.from_dict(item) for item in list(payload.get("skill_specs") or []) if isinstance(item, dict)]
                errors = [{"stage": "intermediate_compile_load", **item} for item in list(payload.get("errors") or []) if isinstance(item, dict)]
        except Exception as exc:
            errors.append({"stage": "intermediate_compile_load", "path": path, "error": str(exc)})
        return SkillCompilationResult(
            support_records=support_records,
            skill_drafts=skill_drafts,
            skill_specs=skill_specs,
            errors=errors,
            compiler_name="llm",
        )

    def write_registration(self, result: "VersionRegistrationResult") -> None:
        """Writes the completed registration snapshot."""

        payload = {
            "documents": [doc.to_dict() for doc in list(result.documents or [])],
            "support_records": [support.to_dict() for support in list(result.support_records or [])],
            "skill_specs": [skill.to_dict() for skill in list(result.skill_specs or [])],
            "hierarchy_updates": [skill.to_dict() for skill in list(result.hierarchy_updates or [])],
            "lifecycles": [item.to_dict() for item in list(result.lifecycles or [])],
            "change_logs": list(result.change_logs or []),
            "version_history": list(result.version_history or []),
            "provenance_links": list(result.provenance_links or []),
            "upserted_store_skills": list(result.upserted_store_skills or []),
            "staging_runs": list(result.staging_runs or []),
            "visible_tree": dict(result.visible_tree or {}),
            "errors": list(result.errors or []),
            "dry_run": bool(result.dry_run),
        }
        self._write_json("register/result.json", payload)
        self._set_stage(
            stage="register_completed",
            completed_stage="register",
            counts={
                "lifecycles": len(result.lifecycles),
                "change_logs": len(result.change_logs),
                "version_history_entries": len(result.version_history),
                "provenance_links": len(result.provenance_links),
                "upserted_store_skills": len(result.upserted_store_skills),
                "staging_runs": len(result.staging_runs),
            },
        )

    def load_registration(self) -> "VersionRegistrationResult":
        """Loads the completed registration snapshot."""

        from ..models import SkillLifecycle, SkillSpec
        from ..store.versioning import VersionRegistrationResult

        path = os.path.join(self.run_dir, "register", "result.json")
        documents: List[DocumentRecord] = []
        support_records: List[SupportRecord] = []
        skill_specs: List[SkillSpec] = []
        hierarchy_updates: List[SkillSpec] = []
        lifecycles: List[SkillLifecycle] = []
        change_logs: List[Dict[str, Any]] = []
        version_history: List[Dict[str, Any]] = []
        provenance_links: List[Dict[str, Any]] = []
        upserted_store_skills: List[Dict[str, Any]] = []
        staging_runs: List[Dict[str, Any]] = []
        visible_tree: Dict[str, Any] = {}
        errors: List[Dict[str, Any]] = []
        dry_run = False
        if not os.path.isfile(path):
            return VersionRegistrationResult(errors=[{"stage": "intermediate_register_load", "error": "register snapshot not found"}])
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                documents = [DocumentRecord.from_dict(item) for item in list(payload.get("documents") or []) if isinstance(item, dict)]
                support_records = [SupportRecord.from_dict(item) for item in list(payload.get("support_records") or []) if isinstance(item, dict)]
                skill_specs = [SkillSpec.from_dict(item) for item in list(payload.get("skill_specs") or []) if isinstance(item, dict)]
                hierarchy_updates = [SkillSpec.from_dict(item) for item in list(payload.get("hierarchy_updates") or []) if isinstance(item, dict)]
                lifecycles = [SkillLifecycle.from_dict(item) for item in list(payload.get("lifecycles") or []) if isinstance(item, dict)]
                change_logs = [dict(item) for item in list(payload.get("change_logs") or []) if isinstance(item, dict)]
                version_history = [dict(item) for item in list(payload.get("version_history") or []) if isinstance(item, dict)]
                provenance_links = [dict(item) for item in list(payload.get("provenance_links") or []) if isinstance(item, dict)]
                upserted_store_skills = [dict(item) for item in list(payload.get("upserted_store_skills") or []) if isinstance(item, dict)]
                staging_runs = [dict(item) for item in list(payload.get("staging_runs") or []) if isinstance(item, dict)]
                visible_tree = dict(payload.get("visible_tree") or {})
                dry_run = bool(payload.get("dry_run"))
                errors = [{"stage": "intermediate_register_load", **item} for item in list(payload.get("errors") or []) if isinstance(item, dict)]
        except Exception as exc:
            errors.append({"stage": "intermediate_register_load", "path": path, "error": str(exc)})
        return VersionRegistrationResult(
            documents=documents,
            support_records=support_records,
            skill_specs=skill_specs,
            hierarchy_updates=hierarchy_updates,
            lifecycles=lifecycles,
            change_logs=change_logs,
            version_history=version_history,
            provenance_links=provenance_links,
            upserted_store_skills=upserted_store_skills,
            staging_runs=staging_runs,
            visible_tree=visible_tree,
            errors=errors,
            dry_run=dry_run,
        )

    def complete(self, *, summary: Optional[Dict[str, Any]] = None) -> None:
        """Marks the intermediate run as completed and optionally writes a summary."""

        if summary:
            self._write_json("final/summary.json", dict(summary or {}))
        self._state["status"] = "completed"
        self._state["updated_at"] = now_iso()
        self._flush_state()

    def fail(self, *, error: str) -> None:
        """Marks the intermediate run as failed."""

        self._state["status"] = "failed"
        self._state["updated_at"] = now_iso()
        self._state["last_error"] = str(error or "").strip()
        self._flush_state()

    def has_completed_stage(self, stage: str) -> bool:
        """Returns whether one stage was already completed in this run."""

        return str(stage or "").strip() in {str(item or "").strip() for item in list(self._state.get("completed_stages") or [])}

    def _write_json(self, relative_path: str, payload: Any) -> str:
        path = os.path.join(self.run_dir, relative_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=False)
        if path not in self._files:
            self._files.append(path)
        self._state["updated_at"] = now_iso()
        self._flush_state()
        return path

    def _set_stage(
        self,
        *,
        stage: str,
        completed_stage: str = "",
        source_file: str = "",
        counts: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._state["current_stage"] = str(stage or "").strip() or self._state.get("current_stage") or "initialized"
        if completed_stage:
            existing = list(self._state.get("completed_stages") or [])
            if completed_stage not in existing:
                existing.append(completed_stage)
            self._state["completed_stages"] = existing
        if source_file:
            self._state["source_file"] = str(source_file or "").strip()
        if counts:
            merged = dict(self._state.get("counts") or {})
            merged.update(dict(counts or {}))
            self._state["counts"] = merged
        self._state["updated_at"] = now_iso()
        self._flush_state()

    def _flush_state(self) -> None:
        os.makedirs(os.path.dirname(self.status_path), exist_ok=True)
        with open(self.status_path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2, sort_keys=False)
