"""
Minimal registry for document offline pipeline entities.

The main skill store persists compiled `SKILL.md` artifacts, but evidence and
capability objects must remain first-class source-of-truth records. This module
stores those objects under a side-car registry rooted at:

<store_root>/.autoskill/document_registry/
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from .models import (
    CapabilitySpec,
    DocumentRecord,
    EvidenceUnit,
    SkillLifecycle,
    SkillSpec,
)
from autoskill.utils.time import now_iso

_ENTITY_LAYOUT = {
    "documents": "documents",
    "evidence": "evidence",
    "capabilities": "capabilities",
    "skills": "skills",
    "lifecycles": "lifecycles",
    "change_logs": "change_logs",
    "provenance_links": "provenance_links",
    "version_history": "version_history",
}


def default_registry_root(store_path: str) -> str:
    """Builds the default document registry path under an AutoSkill store root."""

    root = os.path.abspath(os.path.expanduser(str(store_path or "").strip() or "SkillBank"))
    return os.path.join(root, ".autoskill", "document_registry")


def build_registry_from_store_config(store_config: Dict[str, Any]) -> "DocumentRegistry":
    """Constructs a registry from an AutoSkill store config dict."""

    cfg = dict(store_config or {})
    root = default_registry_root(str(cfg.get("path") or "SkillBank"))
    return DocumentRegistry(root_dir=root)


class DocumentRegistry:
    """
    Filesystem registry for document, evidence, capability, skill, and lifecycle entities.

    Storage format:
    - one JSON file per entity
    - a lightweight manifest under `indexes/manifest.json`
    """

    def __init__(self, *, root_dir: str) -> None:
        """Initializes registry paths and ensures the directory layout exists."""

        self.root_dir = os.path.abspath(os.path.expanduser(str(root_dir or "").strip()))
        if not self.root_dir:
            raise ValueError("registry root_dir must not be empty")
        self.index_dir = os.path.join(self.root_dir, "indexes")
        for dirname in _ENTITY_LAYOUT.values():
            os.makedirs(os.path.join(self.root_dir, dirname), exist_ok=True)
        os.makedirs(self.index_dir, exist_ok=True)
        self._refresh_manifest()

    def upsert_document(self, record: DocumentRecord) -> None:
        """Persists one DocumentRecord to the registry."""

        self._write_entity("documents", record.doc_id, record.to_dict())

    def upsert_evidence(self, unit: EvidenceUnit) -> None:
        """Persists one EvidenceUnit to the registry."""

        self._write_entity("evidence", unit.evidence_id, unit.to_dict())

    def upsert_capability(self, spec: CapabilitySpec) -> None:
        """Persists one CapabilitySpec to the registry."""

        self._write_entity("capabilities", spec.capability_id, spec.to_dict())

    def upsert_skill(self, spec: SkillSpec) -> None:
        """Persists one SkillSpec to the registry."""

        self._write_entity("skills", spec.skill_id, spec.to_dict())

    def append_lifecycle(self, event: SkillLifecycle) -> None:
        """Persists one SkillLifecycle event to the registry."""

        self._write_entity("lifecycles", event.lifecycle_id, event.to_dict())

    def append_change_log(self, change_id: str, payload: Dict[str, Any]) -> None:
        """Persists one version/change event payload."""

        self._write_entity("change_logs", change_id, dict(payload or {}))

    def upsert_provenance_links(
        self,
        *,
        entity_type: str,
        entity_id: str,
        payload: Dict[str, Any],
    ) -> None:
        """Stores the latest provenance links for one registry entity."""

        key = self._compound_key(entity_type=entity_type, entity_id=entity_id)
        self._write_entity("provenance_links", key, dict(payload or {}))

    def append_version_history(
        self,
        *,
        entity_type: str,
        entity_id: str,
        entry: Dict[str, Any],
    ) -> None:
        """Appends one version history entry for a registry entity."""

        key = self._compound_key(entity_type=entity_type, entity_id=entity_id)
        current = self.get_version_history(entity_type=entity_type, entity_id=entity_id)
        current.append(dict(entry or {}))
        self._write_entity("version_history", key, {"entity_type": entity_type, "entity_id": entity_id, "entries": current})

    def get_document(self, doc_id: str) -> Optional[DocumentRecord]:
        """Loads one DocumentRecord by id."""

        obj = self._read_entity("documents", doc_id)
        return DocumentRecord.from_dict(obj) if obj is not None else None

    def get_evidence(self, evidence_id: str) -> Optional[EvidenceUnit]:
        """Loads one EvidenceUnit by id."""

        obj = self._read_entity("evidence", evidence_id)
        return EvidenceUnit.from_dict(obj) if obj is not None else None

    def get_capability(self, capability_id: str) -> Optional[CapabilitySpec]:
        """Loads one CapabilitySpec by id."""

        obj = self._read_entity("capabilities", capability_id)
        return CapabilitySpec.from_dict(obj) if obj is not None else None

    def get_skill(self, skill_id: str) -> Optional[SkillSpec]:
        """Loads one SkillSpec by id."""

        obj = self._read_entity("skills", skill_id)
        return SkillSpec.from_dict(obj) if obj is not None else None

    def get_lifecycle(self, lifecycle_id: str) -> Optional[SkillLifecycle]:
        """Loads one SkillLifecycle by id."""

        obj = self._read_entity("lifecycles", lifecycle_id)
        return SkillLifecycle.from_dict(obj) if obj is not None else None

    def get_version_history(self, *, entity_type: str, entity_id: str) -> List[Dict[str, Any]]:
        """Loads version history entries for one entity."""

        key = self._compound_key(entity_type=entity_type, entity_id=entity_id)
        obj = self._read_entity("version_history", key)
        if not isinstance(obj, dict):
            return []
        entries = obj.get("entries")
        return list(entries) if isinstance(entries, list) else []

    def get_provenance_links(self, *, entity_type: str, entity_id: str) -> Dict[str, Any]:
        """Loads the latest provenance links for one entity."""

        key = self._compound_key(entity_type=entity_type, entity_id=entity_id)
        obj = self._read_entity("provenance_links", key)
        return dict(obj) if isinstance(obj, dict) else {}

    def list_documents(self) -> List[DocumentRecord]:
        """Lists all persisted DocumentRecord objects."""

        return self._list_entities("documents", DocumentRecord)

    def list_evidence(self) -> List[EvidenceUnit]:
        """Lists all persisted EvidenceUnit objects."""

        return self._list_entities("evidence", EvidenceUnit)

    def list_capabilities(self) -> List[CapabilitySpec]:
        """Lists all persisted CapabilitySpec objects."""

        return self._list_entities("capabilities", CapabilitySpec)

    def list_skills(self) -> List[SkillSpec]:
        """Lists all persisted SkillSpec objects."""

        return self._list_entities("skills", SkillSpec)

    def list_lifecycles(self) -> List[SkillLifecycle]:
        """Lists all persisted SkillLifecycle objects."""

        return self._list_entities("lifecycles", SkillLifecycle)

    def list_change_logs(
        self,
        *,
        entity_type: str = "",
        entity_id: str = "",
        action: str = "",
    ) -> List[Dict[str, Any]]:
        """Lists persisted change log payloads with lightweight filtering."""

        out = self._list_plain_entities("change_logs")
        entity_type_s = str(entity_type or "").strip()
        entity_id_s = str(entity_id or "").strip()
        action_s = str(action or "").strip()
        filtered: List[Dict[str, Any]] = []
        for item in out:
            if entity_type_s and str(item.get("entity_type") or "") != entity_type_s:
                continue
            if entity_id_s and str(item.get("entity_id") or "") != entity_id_s:
                continue
            if action_s and str(item.get("action") or "") != action_s:
                continue
            filtered.append(item)
        return filtered

    def find_document_by_content_hash(
        self,
        *,
        doc_id: str = "",
        content_hash: str = "",
        source_file: str = "",
    ) -> Optional[DocumentRecord]:
        """
        Finds an existing document record using stable document identity and content hash.

        Matching strategy:
        - if `doc_id` is provided, it is checked first
        - if `content_hash` is provided, records must match that hash
        - if `source_file` is provided, it is matched against document metadata/source_file
        """

        doc_id_s = str(doc_id or "").strip()
        content_hash_s = str(content_hash or "").strip()
        source_file_s = str(source_file or "").strip()

        if doc_id_s:
            doc = self.get_document(doc_id_s)
            if doc is None:
                return None
            if content_hash_s and str(doc.content_hash or "") != content_hash_s:
                return None
            if source_file_s and str((doc.metadata or {}).get("source_file") or "") != source_file_s:
                return None
            return doc

        if not content_hash_s and not source_file_s:
            return None

        for doc in self.list_documents():
            if content_hash_s and str(doc.content_hash or "") != content_hash_s:
                continue
            if source_file_s and str((doc.metadata or {}).get("source_file") or "") != source_file_s:
                continue
            return doc
        return None

    def list_skills_by_capability_id(self, capability_id: str) -> List[SkillSpec]:
        """Lists persisted SkillSpec records associated with one capability id."""

        cap_id = str(capability_id or "").strip()
        if not cap_id:
            return []
        return [
            skill
            for skill in self.list_skills()
            if str(getattr(skill, "capability_id", "") or "").strip() == cap_id
        ]

    def manifest(self) -> Dict[str, Any]:
        """Loads the last saved manifest from disk."""

        path = os.path.join(self.index_dir, "manifest.json")
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            return {}
        return dict(obj) if isinstance(obj, dict) else {}

    def rebuild_indexes(self) -> Dict[str, Any]:
        """Rebuilds the manifest and returns the new summary."""

        return self._refresh_manifest()

    def _entity_dir(self, kind: str) -> str:
        """Returns one entity directory from a logical kind."""

        dirname = _ENTITY_LAYOUT.get(str(kind or "").strip())
        if not dirname:
            raise ValueError(f"unsupported registry kind: {kind}")
        return os.path.join(self.root_dir, dirname)

    def _entity_path(self, kind: str, entity_id: str) -> str:
        """Builds the path for one entity file."""

        safe_id = str(entity_id or "").strip().replace("/", "_")
        if not safe_id:
            raise ValueError("entity_id must not be empty")
        return os.path.join(self._entity_dir(kind), f"{safe_id}.json")

    def _compound_key(self, *, entity_type: str, entity_id: str) -> str:
        """Builds a stable compound key for sidecar registry objects."""

        entity_type_s = str(entity_type or "").strip()
        entity_id_s = str(entity_id or "").strip()
        if not entity_type_s or not entity_id_s:
            raise ValueError("entity_type and entity_id must not be empty")
        return f"{entity_type_s}__{entity_id_s}"

    def _write_entity(self, kind: str, entity_id: str, payload: Dict[str, Any]) -> None:
        """Writes one entity atomically and refreshes the manifest."""

        path = self._entity_path(kind, entity_id)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=False)
        os.replace(tmp, path)
        self._refresh_manifest()

    def _read_entity(self, kind: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Reads one entity file if present."""

        path = self._entity_path(kind, entity_id)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            return None
        return dict(obj) if isinstance(obj, dict) else None

    def _list_entities(self, kind: str, model_cls: Any) -> List[Any]:
        """Loads all entity JSON files for one registry kind."""

        root = self._entity_dir(kind)
        out: List[Any] = []
        for name in sorted(os.listdir(root)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    obj = json.load(f)
            except Exception:
                continue
            if isinstance(obj, dict):
                try:
                    out.append(model_cls.from_dict(obj))
                except Exception:
                    continue
        return out

    def _list_plain_entities(self, kind: str) -> List[Dict[str, Any]]:
        """Loads all plain JSON objects for one registry kind."""

        root = self._entity_dir(kind)
        out: List[Dict[str, Any]] = []
        for name in sorted(os.listdir(root)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    obj = json.load(f)
            except Exception:
                continue
            if isinstance(obj, dict):
                out.append(dict(obj))
        return out

    def _refresh_manifest(self) -> Dict[str, Any]:
        """Recomputes and saves a lightweight registry manifest."""

        entities: Dict[str, Dict[str, Any]] = {}
        for kind in _ENTITY_LAYOUT:
            root = self._entity_dir(kind)
            ids = sorted(
                name[:-5]
                for name in os.listdir(root)
                if name.endswith(".json") and os.path.isfile(os.path.join(root, name))
            )
            entities[kind] = {"count": len(ids), "ids": ids}

        manifest = {
            "saved_at": now_iso(),
            "root_dir": self.root_dir,
            "entities": entities,
        }
        path = os.path.join(self.index_dir, "manifest.json")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=False)
        os.replace(tmp, path)
        return manifest
