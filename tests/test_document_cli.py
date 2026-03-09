from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import os
import tempfile
import unittest

from autoskill.cli import main as autoskill_main
from autoskill.offline.document.extract import main


_DOC_TEXT = """
# Method
1. Gather source inputs before classification.
2. Normalize fields before applying the workflow.

# Constraints
You must verify required fields before running the workflow.
Do not continue when key inputs are missing.
""".strip()


class DocumentCliTest(unittest.TestCase):
    def _write_doc(self, *, root: str) -> str:
        path = os.path.join(root, "document.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(_DOC_TEXT)
        return path

    def _run_main_json(self, argv: list[str]) -> dict:
        buf = io.StringIO()
        with redirect_stdout(buf):
            main(argv)
        text = buf.getvalue().strip()
        self.assertTrue(text)
        return json.loads(text)

    def _run_text(self, fn, argv: list[str]) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            try:
                fn(argv)
            except SystemExit as exc:
                if int(getattr(exc, "code", 0) or 0) not in {0}:
                    raise
        return buf.getvalue()

    def test_default_cli_invocation_routes_to_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_path = self._write_doc(root=tmpdir)
            payload = self._run_main_json(
                [
                    "--file",
                    doc_path,
                    "--dry-run",
                    "--quiet",
                    "--json",
                    "--llm-provider",
                    "mock",
                    "--maintenance-strategy",
                    "heuristic",
                    "--store-path",
                    tmpdir,
                ]
            )

            self.assertEqual(payload["total_documents"], 1)
            self.assertGreater(payload["total_evidence_units"], 0)
            self.assertGreater(payload["total_capabilities"], 0)
            self.assertGreater(payload["total_skill_specs"], 0)

    def test_extract_command_returns_evidence_units(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_path = self._write_doc(root=tmpdir)
            payload = self._run_main_json(
                [
                    "extract",
                    "--file",
                    doc_path,
                    "--dry-run",
                    "--quiet",
                    "--json",
                    "--llm-provider",
                    "mock",
                    "--maintenance-strategy",
                    "heuristic",
                    "--store-path",
                    tmpdir,
                ]
            )

            self.assertEqual(len(payload["documents"]), 1)
            self.assertGreater(len(payload["evidence_units"]), 0)
            self.assertIn("claim_type", payload["evidence_units"][0])

    def test_induce_command_returns_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_path = self._write_doc(root=tmpdir)
            payload = self._run_main_json(
                [
                    "induce",
                    "--file",
                    doc_path,
                    "--dry-run",
                    "--quiet",
                    "--json",
                    "--llm-provider",
                    "mock",
                    "--maintenance-strategy",
                    "heuristic",
                    "--store-path",
                    tmpdir,
                ]
            )

            self.assertEqual(len(payload["documents"]), 1)
            self.assertGreater(len(payload["capabilities"]), 0)
            self.assertIn("capability_id", payload["capabilities"][0])

    def test_top_level_cli_routes_to_document_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_path = self._write_doc(root=tmpdir)
            buf = io.StringIO()
            with redirect_stdout(buf):
                autoskill_main(
                    [
                        "offline",
                        "document",
                        "compile",
                        "--file",
                        doc_path,
                        "--dry-run",
                        "--quiet",
                        "--json",
                        "--llm-provider",
                        "mock",
                        "--maintenance-strategy",
                        "heuristic",
                        "--store-path",
                        tmpdir,
                    ]
                )
            payload = json.loads(buf.getvalue().strip())

            self.assertEqual(len(payload["documents"]), 1)
            self.assertGreater(len(payload["evidence_units"]), 0)
            self.assertGreater(len(payload["capabilities"]), 0)
            self.assertGreater(len(payload["skills"]), 0)

    def test_top_level_document_help_shows_document_subcommands(self) -> None:
        output = self._run_text(autoskill_main, ["offline", "document", "-h"])

        self.assertIn("build", output)
        self.assertIn("ingest", output)
        self.assertIn("extract", output)
        self.assertIn("induce", output)
        self.assertIn("compile", output)

    def test_build_help_includes_examples_and_registry_help(self) -> None:
        output = self._run_text(main, ["build", "-h"])

        self.assertIn("Examples:", output)
        self.assertIn("--registry-root", output)
        self.assertIn("document registry root", output)


if __name__ == "__main__":
    unittest.main()
