from __future__ import annotations

import os
import tempfile
import unittest

from autoskill.offline.document.models import (
    CapabilitySpec,
    DocumentRecord,
    EvidenceUnit,
    ProvenanceRecord,
    SkillSpec,
    TextSpan,
    VersionState,
)
from autoskill.offline.document.registry import DocumentRegistry
from autoskill.offline.document.versioning import register_versions


class DocumentVersioningTest(unittest.TestCase):
    def _registry(self) -> DocumentRegistry:
        self._tmpdir = tempfile.TemporaryDirectory()
        return DocumentRegistry(root_dir=os.path.join(self._tmpdir.name, "registry"))

    def tearDown(self) -> None:
        tmp = getattr(self, "_tmpdir", None)
        if tmp is not None:
            tmp.cleanup()

    def _document(self, doc_id: str, title: str) -> DocumentRecord:
        return DocumentRecord(
            doc_id=doc_id,
            source_type="document",
            title=title,
            raw_text=title,
            content_hash=f"hash-{doc_id}",
            metadata={"source_file": f"/tmp/{doc_id}.md"},
        )

    def _evidence(
        self,
        evidence_id: str,
        doc_id: str,
        claim: str,
        *,
        task_family: str = "analysis",
        method_family: str = "workflow",
        conflicts_with: list[str] | None = None,
    ) -> EvidenceUnit:
        return EvidenceUnit(
            evidence_id=evidence_id,
            doc_id=doc_id,
            claim_type="workflow_step",
            section="Method",
            span=TextSpan(start=0, end=len(claim)),
            normalized_claim=claim,
            verbatim_excerpt=claim,
            task_family=task_family,
            method_family=method_family,
            confidence=0.8,
            conflicts_with=list(conflicts_with or []),
            provenance=ProvenanceRecord(
                source_type="document",
                source_file=f"/tmp/{doc_id}.md",
                section="Method",
                span=TextSpan(start=0, end=len(claim)),
            ),
        )

    def _capability(
        self,
        capability_id: str,
        title: str,
        evidence_refs: list[str],
        workflow_steps: list[str],
        *,
        task_family: str = "analysis",
        method_family: str = "workflow",
        stage: str = "execution",
        constraints: list[str] | None = None,
        version: str = "0.1.0",
        status: VersionState = VersionState.ACTIVE,
    ) -> CapabilitySpec:
        return CapabilitySpec(
            capability_id=capability_id,
            title=title,
            domain="geography",
            task_family=task_family,
            method_family=method_family,
            stage=stage,
            workflow_steps=workflow_steps,
            constraints=list(constraints or ["Verify required fields."]),
            evidence_refs=evidence_refs,
            version=version,
            status=status,
        )

    def _skill(
        self,
        skill_id: str,
        capability_id: str,
        name: str,
        *,
        version: str = "0.1.0",
        status: VersionState = VersionState.ACTIVE,
    ) -> SkillSpec:
        return SkillSpec(
            skill_id=skill_id,
            capability_id=capability_id,
            name=name,
            description=f"Skill for {name}.",
            skill_body="# Goal\nExecute workflow.",
            references=[capability_id],
            metadata={"compiled_tags": ["analysis"], "compiled_triggers": ["Use when analysis is requested."]},
            version=version,
            status=status,
        )

    def _seed_existing(
        self,
        registry: DocumentRegistry,
        *,
        document: DocumentRecord,
        evidence: list[EvidenceUnit],
        capability: CapabilitySpec,
        skill: SkillSpec,
    ) -> None:
        registry.upsert_document(document)
        for unit in evidence:
            registry.upsert_evidence(unit)
        registry.upsert_capability(capability)
        registry.upsert_skill(skill)

    def test_new_skill_create(self) -> None:
        registry = self._registry()
        document = self._document("doc-new", "New workflow")
        evidence = [self._evidence("ev-new", document.doc_id, "Collect inputs before analysis.")]
        capability = self._capability("cap-new", "Analysis workflow", [evidence[0].evidence_id], ["Collect inputs", "Run analysis"])
        skill = self._skill("skill-new", capability.capability_id, "analysis-workflow")

        result = register_versions(
            registry=registry,
            documents=[document],
            evidence_units=evidence,
            capabilities=[capability],
            skill_specs=[skill],
            dry_run=False,
        )

        self.assertEqual(result.capabilities[0].version, "0.1.0")
        self.assertEqual(result.skill_specs[0].version, "0.1.0")
        self.assertTrue(any(log["action"] == "create" for log in result.change_logs))
        self.assertEqual(len(registry.get_version_history(entity_type="capability", entity_id="cap-new")), 1)

    def test_same_skill_update_strengthens_existing_capability(self) -> None:
        registry = self._registry()
        existing_doc = self._document("doc-old", "Existing workflow")
        existing_evidence = [self._evidence("ev-old", existing_doc.doc_id, "Collect inputs before analysis.")]
        existing_capability = self._capability("cap-existing", "Analysis workflow", [existing_evidence[0].evidence_id], ["Collect inputs", "Run analysis"])
        existing_skill = self._skill("skill-existing", existing_capability.capability_id, "analysis-workflow")
        self._seed_existing(
            registry,
            document=existing_doc,
            evidence=existing_evidence,
            capability=existing_capability,
            skill=existing_skill,
        )

        new_doc = self._document("doc-new", "Updated workflow")
        new_evidence = [
            self._evidence("ev-old", existing_doc.doc_id, "Collect inputs before analysis."),
            self._evidence("ev-new", new_doc.doc_id, "Collect inputs before analysis."),
        ]
        new_capability = self._capability(
            "cap-candidate",
            "Analysis workflow",
            [unit.evidence_id for unit in new_evidence],
            ["Collect inputs", "Run analysis"],
        )
        new_skill = self._skill("skill-candidate", new_capability.capability_id, "analysis-workflow")

        result = register_versions(
            registry=registry,
            documents=[new_doc],
            evidence_units=new_evidence,
            capabilities=[new_capability],
            skill_specs=[new_skill],
            dry_run=False,
        )

        updated = [cap for cap in result.capabilities if cap.capability_id == "cap-existing"][-1]
        self.assertEqual(updated.version, "0.1.1")
        self.assertEqual(updated.status, VersionState.ACTIVE)
        self.assertTrue(any(log["action"] == "strengthen" for log in result.change_logs))
        provenance = registry.get_provenance_links(entity_type="capability", entity_id="cap-existing")
        self.assertIn("doc-new", provenance.get("doc_ids", []))
        self.assertIn("ev-new", provenance.get("evidence_added", []))

    def test_skill_split(self) -> None:
        registry = self._registry()
        existing_doc = self._document("doc-old", "Broad workflow")
        existing_evidence = [self._evidence("ev-old", existing_doc.doc_id, "Collect inputs normalize inputs generate report archive output.")]
        existing_capability = self._capability(
            "cap-broad",
            "Analysis workflow",
            [existing_evidence[0].evidence_id],
            ["Collect inputs", "Normalize inputs", "Generate report", "Archive output"],
        )
        existing_skill = self._skill("skill-broad", existing_capability.capability_id, "analysis-workflow")
        self._seed_existing(
            registry,
            document=existing_doc,
            evidence=existing_evidence,
            capability=existing_capability,
            skill=existing_skill,
        )

        new_doc = self._document("doc-split", "Split workflow")
        new_evidence = [
            self._evidence("ev-s1", new_doc.doc_id, "Collect inputs and normalize inputs."),
            self._evidence("ev-s2", new_doc.doc_id, "Generate report and archive output."),
        ]
        child_a = self._capability(
            "cap-child-a",
            "Analysis workflow",
            ["ev-s1"],
            ["Collect inputs", "Normalize inputs"],
        )
        child_b = self._capability(
            "cap-child-b",
            "Analysis workflow",
            ["ev-s2"],
            ["Generate report", "Archive output"],
        )
        skill_a = self._skill("skill-child-a", child_a.capability_id, "analysis-workflow-a")
        skill_b = self._skill("skill-child-b", child_b.capability_id, "analysis-workflow-b")

        result = register_versions(
            registry=registry,
            documents=[new_doc],
            evidence_units=new_evidence,
            capabilities=[child_a, child_b],
            skill_specs=[skill_a, skill_b],
            dry_run=False,
        )

        self.assertTrue(any(log["action"] == "split" for log in result.change_logs))
        deprecated_parent = registry.get_capability("cap-broad")
        self.assertEqual(deprecated_parent.status, VersionState.DEPRECATED)
        self.assertIsNotNone(registry.get_capability("cap-child-a"))
        self.assertIsNotNone(registry.get_capability("cap-child-b"))

    def test_skill_merge(self) -> None:
        registry = self._registry()
        doc_a = self._document("doc-a", "Workflow A")
        doc_b = self._document("doc-b", "Workflow B")
        evidence_a = [self._evidence("ev-a", doc_a.doc_id, "Collect inputs and normalize inputs.")]
        evidence_b = [self._evidence("ev-b", doc_b.doc_id, "Generate report and archive output.")]
        capability_a = self._capability(
            "cap-a",
            "Analysis workflow",
            ["ev-a"],
            ["Collect inputs", "Normalize inputs"],
            constraints=["Verify required fields."],
        )
        capability_b = self._capability(
            "cap-b",
            "Analysis workflow",
            ["ev-b"],
            ["Generate report", "Archive output"],
            constraints=["Verify required fields."],
        )
        skill_a = self._skill("skill-a", capability_a.capability_id, "analysis-workflow-a")
        skill_b = self._skill("skill-b", capability_b.capability_id, "analysis-workflow-b")
        self._seed_existing(registry, document=doc_a, evidence=evidence_a, capability=capability_a, skill=skill_a)
        self._seed_existing(registry, document=doc_b, evidence=evidence_b, capability=capability_b, skill=skill_b)

        merged_doc = self._document("doc-merged", "Merged workflow")
        merged_evidence = [self._evidence("ev-merged", merged_doc.doc_id, "Collect inputs normalize inputs generate report archive output.")]
        merged_capability = self._capability(
            "cap-merged",
            "Analysis workflow",
            ["ev-merged"],
            ["Collect inputs", "Normalize inputs", "Generate report", "Archive output"],
            constraints=["Verify required fields."],
        )
        merged_skill = self._skill("skill-merged", merged_capability.capability_id, "analysis-workflow")

        result = register_versions(
            registry=registry,
            documents=[merged_doc],
            evidence_units=merged_evidence,
            capabilities=[merged_capability],
            skill_specs=[merged_skill],
            dry_run=False,
        )

        self.assertTrue(any(log["action"] == "merge" for log in result.change_logs))
        deprecated_ids = [
            cap_id
            for cap_id in ["cap-a", "cap-b"]
            if registry.get_capability(cap_id).status == VersionState.DEPRECATED
        ]
        active_or_draft_ids = [
            cap_id
            for cap_id in ["cap-a", "cap-b"]
            if registry.get_capability(cap_id).status in {VersionState.ACTIVE, VersionState.DRAFT}
        ]
        self.assertEqual(len(deprecated_ids), 1)
        self.assertEqual(len(active_or_draft_ids), 1)
        self.assertEqual(registry.get_capability(active_or_draft_ids[0]).version, "0.1.1")

    def test_skill_deprecate(self) -> None:
        registry = self._registry()
        old_doc = self._document("doc-old", "Manual workflow")
        old_evidence = [self._evidence("ev-old", old_doc.doc_id, "Classify observations manually.")]
        old_capability = self._capability(
            "cap-old",
            "Manual classification workflow",
            ["ev-old"],
            ["Classify observations manually"],
            task_family="classification",
        )
        old_skill = self._skill("skill-old", old_capability.capability_id, "manual-classification")
        self._seed_existing(
            registry,
            document=old_doc,
            evidence=old_evidence,
            capability=old_capability,
            skill=old_skill,
        )

        new_doc = self._document("doc-new", "Automated workflow")
        new_evidence = [self._evidence("ev-new", new_doc.doc_id, "Do not classify observations manually use automated extraction.", task_family="classification", conflicts_with=["ev-old"])]
        new_capability = self._capability(
            "cap-new",
            "Automated extraction workflow",
            ["ev-new"],
            ["Use automated extraction", "Review extracted output"],
            task_family="classification",
        )
        new_skill = self._skill("skill-new", new_capability.capability_id, "automated-extraction")

        result = register_versions(
            registry=registry,
            documents=[new_doc],
            evidence_units=new_evidence,
            capabilities=[new_capability],
            skill_specs=[new_skill],
            dry_run=False,
        )

        self.assertTrue(any(log["action"] == "deprecate" for log in result.change_logs))
        deprecated = registry.get_capability("cap-old")
        self.assertIn(deprecated.status, {VersionState.WATCHLIST, VersionState.DEPRECATED})


if __name__ == "__main__":
    unittest.main()
