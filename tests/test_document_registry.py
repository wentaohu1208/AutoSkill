from __future__ import annotations

import os
import tempfile
import unittest

from autoskill.offline.document.models import (
    CapabilitySpec,
    DocumentRecord,
    EvidenceUnit,
    ProvenanceRecord,
    SkillLifecycle,
    SkillSpec,
    TextSpan,
    VersionState,
)
from autoskill.offline.document.registry import (
    DocumentRegistry,
    build_registry_from_store_config,
    default_registry_root,
)


class DocumentRegistryTest(unittest.TestCase):
    def test_default_registry_root_uses_store_root(self) -> None:
        root = default_registry_root("/tmp/SkillBank")
        self.assertEqual(root, os.path.join("/tmp/SkillBank", ".autoskill", "document_registry"))

    def test_registry_persists_entities_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = DocumentRegistry(root_dir=os.path.join(tmpdir, "registry"))

            document = DocumentRecord(
                doc_id="doc-1",
                source_type="paper",
                title="Workflow extraction",
                raw_text="A reproducible method.",
                content_hash="hash-1",
            )
            evidence = EvidenceUnit(
                evidence_id="ev-1",
                doc_id=document.doc_id,
                claim_type="workflow_step",
                normalized_claim="Collect input before applying rules.",
                section="Method",
                span=TextSpan(start=0, end=12),
                confidence=0.9,
                provenance=ProvenanceRecord(
                    source_type="paper",
                    source_file="/tmp/paper.md",
                    section="Method",
                    span=TextSpan(start=0, end=12),
                ),
            )
            capability = CapabilitySpec(
                capability_id="cap-1",
                title="Rule-grounded transformation",
                workflow_steps=["Collect input", "Apply rules"],
                decision_rules=["Stop when required input is missing."],
                evidence_refs=[evidence.evidence_id],
            )
            skill = SkillSpec(
                skill_id="skill-1",
                capability_id=capability.capability_id,
                name="rule-grounded-transformation",
                description="Compiles a rule-grounded transformation workflow.",
                skill_body="# Goal\nTransform with rules.",
                status=VersionState.DRAFT,
            )
            lifecycle = SkillLifecycle(
                lifecycle_id="life-1",
                skill_id=skill.skill_id,
                capability_id=capability.capability_id,
                to_state=VersionState.DRAFT,
            )

            registry.upsert_document(document)
            registry.upsert_evidence(evidence)
            registry.upsert_capability(capability)
            registry.upsert_skill(skill)
            registry.append_lifecycle(lifecycle)
            registry.append_version_history(
                entity_type="capability",
                entity_id=capability.capability_id,
                entry={"entity_type": "capability", "entity_id": capability.capability_id, "version": "0.1.0"},
            )
            registry.append_change_log(
                "chg-1",
                {"change_id": "chg-1", "entity_type": "capability", "entity_id": capability.capability_id, "action": "create"},
            )
            registry.upsert_provenance_links(
                entity_type="capability",
                entity_id=capability.capability_id,
                payload={"entity_type": "capability", "entity_id": capability.capability_id, "doc_ids": [document.doc_id]},
            )

            self.assertEqual(registry.get_document(document.doc_id).title, document.title)
            self.assertEqual(registry.get_evidence(evidence.evidence_id).doc_id, document.doc_id)
            self.assertEqual(
                registry.get_capability(capability.capability_id).title,
                capability.title,
            )
            self.assertEqual(registry.get_skill(skill.skill_id).name, skill.name)
            self.assertEqual(
                registry.get_lifecycle(lifecycle.lifecycle_id).to_state,
                VersionState.DRAFT,
            )
            self.assertEqual(len(registry.get_version_history(entity_type="capability", entity_id=capability.capability_id)), 1)
            self.assertEqual(len(registry.list_change_logs(entity_type="capability", entity_id=capability.capability_id)), 1)
            self.assertEqual(
                registry.get_provenance_links(entity_type="capability", entity_id=capability.capability_id).get("doc_ids"),
                [document.doc_id],
            )

            manifest = registry.manifest()
            self.assertEqual(manifest["entities"]["documents"]["count"], 1)
            self.assertEqual(manifest["entities"]["skills"]["count"], 1)

    def test_build_registry_from_store_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = build_registry_from_store_config({"provider": "local", "path": tmpdir})
            self.assertTrue(registry.root_dir.startswith(tmpdir))
            self.assertTrue(os.path.isdir(registry.root_dir))


if __name__ == "__main__":
    unittest.main()
