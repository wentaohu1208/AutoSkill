from __future__ import annotations

import json
import unittest

from autoskill.offline.document.models import (
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


class DocumentModelsTest(unittest.TestCase):
    def test_document_record_serialization_round_trip(self) -> None:
        record = DocumentRecord(
            doc_id="doc-1",
            source_type="journal_article",
            title="Structured Analysis of Field Workflows",
            authors=["A. Researcher", "B. Reviewer"],
            year=2024,
            domain="geography",
            raw_text="Intro\n\nMethod\n\nConclusion",
            sections=[
                DocumentSection(
                    heading="Method",
                    text="Step 1. Gather observations.",
                    level=2,
                    span=TextSpan(start=6, end=34),
                )
            ],
            metadata={"journal": "Cross Domain Methods"},
            checksum="abc123",
        )

        payload = record.to_dict()
        self.assertEqual(payload["doc_id"], "doc-1")
        self.assertEqual(payload["content_hash"], "abc123")

        restored = DocumentRecord.from_json(record.to_json())
        self.assertEqual(restored.doc_id, record.doc_id)
        self.assertEqual(restored.sections[0].heading, "Method")
        self.assertIn("source_type: journal_article", record.to_yaml())

    def test_evidence_capability_skill_round_trip(self) -> None:
        evidence = EvidenceUnit(
            evidence_id="ev-1",
            doc_id="doc-1",
            claim_type="workflow_step",
            section="Method",
            span=TextSpan(start=10, end=40),
            normalized_claim="Gather observations before classification.",
            verbatim_excerpt="Step 1. Gather observations before classification.",
            method_family="field-study",
            task_family="classification",
            confidence=0.8,
            provenance=ProvenanceRecord(
                source_type="journal_article",
                source_file="/tmp/doc.md",
                section="Method",
                span=TextSpan(start=10, end=40),
            ),
        )
        capability = CapabilitySpec(
            capability_id="cap-1",
            title="Observation-first classification",
            domain="geography",
            task_family="classification",
            method_family="field-study",
            stage="analysis",
            workflow_steps=["Collect observations", "Classify by observed features"],
            decision_rules=["If evidence is incomplete, defer classification."],
            constraints=["Do not classify from speculation alone."],
            failure_modes=["Insufficient observations"],
            output_contract={"type": "report", "fields": ["label", "rationale"]},
            risk_class="medium",
            evidence_refs=[evidence.evidence_id],
            version="0.1.0",
        )
        skill = SkillSpec(
            skill_id="skill-1",
            capability_id=capability.capability_id,
            name="observation-first-classification",
            description="Performs observation-grounded classification workflows.",
            skill_body="# Goal\nClassify using observed evidence.",
            references=[evidence.evidence_id, capability.capability_id],
            metadata={"domain": "geography"},
            version="0.1.0",
            status=VersionState.ACTIVE,
        )
        lifecycle = SkillLifecycle(
            lifecycle_id="life-1",
            skill_id=skill.skill_id,
            capability_id=capability.capability_id,
            from_state=VersionState.DRAFT,
            to_state=VersionState.ACTIVE,
            reason="Validated on initial corpus.",
        )

        ev2 = EvidenceUnit.from_dict(json.loads(evidence.to_json()))
        cap2 = CapabilitySpec.from_dict(json.loads(capability.to_json()))
        skill2 = SkillSpec.from_dict(json.loads(skill.to_json()))
        lifecycle2 = SkillLifecycle.from_dict(json.loads(lifecycle.to_json()))

        self.assertEqual(ev2.normalized_claim, evidence.normalized_claim)
        self.assertEqual(cap2.evidence_refs, [evidence.evidence_id])
        self.assertEqual(skill2.status, VersionState.ACTIVE)
        self.assertEqual(lifecycle2.to_state, VersionState.ACTIVE)

    def test_validation_rejects_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            EvidenceUnit(
                evidence_id="ev-1",
                doc_id="doc-1",
                claim_type="constraint",
                normalized_claim="Must verify the source.",
                confidence=1.5,
                provenance=ProvenanceRecord(source_type="doc"),
            )

        with self.assertRaises(ValueError):
            CapabilitySpec(
                capability_id="cap-1",
                title="Broken capability",
                evidence_refs=[],
                version="v1",
            )

        with self.assertRaises(ValueError):
            SkillLifecycle(
                lifecycle_id="life-1",
                skill_id="skill-1",
                from_state=VersionState.ACTIVE,
                to_state=VersionState.ACTIVE,
            )


if __name__ == "__main__":
    unittest.main()
