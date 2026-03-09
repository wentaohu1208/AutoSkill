from __future__ import annotations

import tempfile
import unittest

from autoskill import AutoSkill, AutoSkillConfig
from autoskill.offline.document.extract import extract_from_doc
from autoskill.offline.document.pipeline import build_default_document_pipeline


_DOC_TEXT = """
# Method
1. Gather source inputs before classification.
2. Normalize fields before applying the workflow.

# Constraints
You must verify required fields before running the workflow.
Do not continue when key inputs are missing.

# Validation
If evidence is incomplete, report uncertainty instead of forcing a result.

# Output
Output a report with label and rationale.
""".strip()


class DocumentPipelineTest(unittest.TestCase):
    def _build_sdk(self, *, store_path: str) -> AutoSkill:
        return AutoSkill(
            AutoSkillConfig(
                llm={"provider": "mock"},
                embeddings={"provider": "hashing", "dims": 64},
                store={"provider": "local", "path": store_path},
                maintenance_strategy="heuristic",
            )
        )

    def test_full_build_persists_registry_and_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sdk = self._build_sdk(store_path=tmpdir)
            logs: list[str] = []
            pipeline = build_default_document_pipeline(sdk=sdk, logger=logs.append)

            result = pipeline.build(
                user_id="u1",
                data=_DOC_TEXT,
                title="Classification Workflow",
                domain="geography",
                metadata={"channel": "offline_extract_from_doc"},
            )

            self.assertEqual(len(result.ingest.documents), 1)
            self.assertGreater(len(result.evidence.evidence_units), 0)
            self.assertGreater(len(result.capabilities.capabilities), 0)
            self.assertGreater(len(result.skills.skill_specs), 0)
            self.assertGreater(len(result.registration.lifecycles), 0)
            self.assertGreaterEqual(len(result.registration.upserted_store_skills), 1)
            self.assertEqual(pipeline.registry.manifest()["entities"]["documents"]["count"], 1)
            self.assertGreaterEqual(pipeline.registry.manifest()["entities"]["skills"]["count"], 1)
            self.assertGreaterEqual(len(sdk.store.list(user_id="u1")), 1)
            self.assertTrue(any("[ingest_document]" in line for line in logs))
            self.assertTrue(any("[extract_evidence]" in line for line in logs))
            self.assertTrue(any("[compile_skills]" in line for line in logs))

    def test_incremental_build_skips_unchanged_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sdk = self._build_sdk(store_path=tmpdir)
            pipeline = build_default_document_pipeline(sdk=sdk)

            first = pipeline.build(
                user_id="u1",
                data=_DOC_TEXT,
                title="Classification Workflow",
                domain="geography",
                metadata={"channel": "offline_extract_from_doc"},
            )
            second = pipeline.build(
                user_id="u1",
                data=_DOC_TEXT,
                title="Classification Workflow",
                domain="geography",
                metadata={"channel": "offline_extract_from_doc"},
            )

            self.assertEqual(len(first.ingest.documents), 1)
            self.assertEqual(len(second.ingest.documents), 0)
            self.assertEqual(len(second.ingest.skipped_documents), 1)
            self.assertEqual(len(second.registration.skill_specs), 0)

    def test_dry_run_does_not_persist_registry_or_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sdk = self._build_sdk(store_path=tmpdir)
            pipeline = build_default_document_pipeline(sdk=sdk)

            result = pipeline.build(
                user_id="u1",
                data=_DOC_TEXT,
                title="Classification Workflow",
                domain="geography",
                metadata={"channel": "offline_extract_from_doc"},
                dry_run=True,
            )

            manifest = pipeline.registry.manifest()
            self.assertTrue(result.dry_run)
            self.assertGreater(len(result.registration.lifecycles), 0)
            self.assertEqual(manifest["entities"]["documents"]["count"], 0)
            self.assertEqual(manifest["entities"]["skills"]["count"], 0)
            self.assertEqual(len(sdk.store.list(user_id="u1")), 0)

    def test_extract_from_doc_returns_stage_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sdk = self._build_sdk(store_path=tmpdir)

            result = extract_from_doc(
                sdk=sdk,
                user_id="u1",
                data=_DOC_TEXT,
                title="Classification Workflow",
                domain="geography",
                metadata={"channel": "offline_extract_from_doc"},
                dry_run=True,
            )

            self.assertEqual(result["total_documents"], 1)
            self.assertGreater(result["total_evidence_units"], 0)
            self.assertGreater(result["total_capabilities"], 0)
            self.assertGreater(result["total_skill_specs"], 0)
            self.assertEqual(result["upserted_count"], 0)
            self.assertTrue(result["dry_run"])

    def test_compile_stage_keeps_references_outside_skill_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sdk = self._build_sdk(store_path=tmpdir)
            pipeline = build_default_document_pipeline(sdk=sdk)

            ingest_result = pipeline.ingest_document(
                data=_DOC_TEXT,
                title="Classification Workflow",
                domain="geography",
                metadata={"channel": "offline_extract_from_doc"},
                dry_run=True,
            )
            evidence_result = pipeline.extract_evidence(documents=ingest_result.documents)
            capability_result = pipeline.induce_capabilities(
                documents=ingest_result.documents,
                evidence_units=evidence_result.evidence_units,
            )
            skill_result = pipeline.compile_skills(capabilities=capability_result.capabilities)

            spec = skill_result.skill_specs[0]
            capability = capability_result.capabilities[0]
            first_ref = capability.evidence_refs[0]

            self.assertEqual(spec.references, capability.evidence_refs)
            self.assertEqual(
                spec.metadata.get("evidence_ref_count"),
                len(capability.evidence_refs),
            )
            self.assertNotIn(first_ref, spec.skill_body)
            self.assertNotIn("source_file", spec.skill_body.lower())
            self.assertNotIn("confidence", spec.skill_body.lower())

    def test_changed_document_bumps_registry_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sdk = self._build_sdk(store_path=tmpdir)
            pipeline = build_default_document_pipeline(sdk=sdk)
            initial_text = """
# Method
1. Normalize source fields.
2. Apply the workflow.

# Constraints
You must verify required fields before execution.
""".strip()
            revised_text = """
# Method
1. Normalize source fields.
2. Apply the workflow.

# Constraints
You must verify required fields before execution.
Always record provenance for each required field.
""".strip()

            first = pipeline.build(
                user_id="u1",
                data=initial_text,
                title="Normalization Workflow",
                domain="geography",
                metadata={"channel": "offline_extract_from_doc"},
            )
            second = pipeline.build(
                user_id="u1",
                data=revised_text,
                title="Normalization Workflow",
                domain="geography",
                metadata={"channel": "offline_extract_from_doc"},
            )

            first_versions = {
                spec.capability_id: spec.version for spec in list(first.registration.capabilities or [])
            }
            shared_capabilities = [
                spec for spec in list(second.registration.capabilities or []) if spec.capability_id in first_versions
            ]

            self.assertTrue(shared_capabilities)
            self.assertTrue(any(spec.version != first_versions[spec.capability_id] for spec in shared_capabilities))
            self.assertTrue(any(spec.version == "0.1.1" for spec in shared_capabilities))
            self.assertTrue(
                any(event.reason in {"revise", "strengthen", "merge"} for event in second.registration.lifecycles)
            )


if __name__ == "__main__":
    unittest.main()
