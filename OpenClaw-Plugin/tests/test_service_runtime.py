from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLUGIN_DIR = _REPO_ROOT / "OpenClaw-Plugin"
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from autoskill.interactive.server import AutoSkillProxyConfig  # noqa: E402
from openclaw_conversation_archive import OpenClawConversationArchiveConfig  # noqa: E402
from openclaw_main_turn_proxy import OpenClawMainTurnProxyConfig  # noqa: E402
from openclaw_skill_mirror import OpenClawSkillInstallConfig  # noqa: E402
from service_runtime import OpenClawSkillRuntime  # noqa: E402


class _FakeSDK:
    def ingest(self, *, user_id: str, messages: List[Dict[str, Any]], metadata: Dict[str, Any], hint: str | None = None) -> List[Any]:
        return []


class OpenClawServiceRuntimeTest(unittest.TestCase):
    def _make_runtime(
        self,
        *,
        archive_dir: str,
        main_turn_enabled: bool = False,
        target_base_url: str = "",
    ) -> OpenClawSkillRuntime:
        return OpenClawSkillRuntime(
            sdk=_FakeSDK(),
            llm_config={"provider": "mock", "response": ""},
            embeddings_config={"provider": "hashing", "dims": 32},
            config=AutoSkillProxyConfig(
                user_id="u-test",
                extract_enabled=True,
                ingest_window=6,
                top_k=1,
            ).normalize(),
            main_turn_proxy_config=OpenClawMainTurnProxyConfig(
                enabled=main_turn_enabled,
                target_base_url=target_base_url,
                ingest_window=6,
                agent_end_extract_enabled=True,
            ).normalize(),
            skill_install_config=OpenClawSkillInstallConfig(mode="store_only").normalize(),
            conversation_archive_config=OpenClawConversationArchiveConfig(
                enabled=True,
                archive_dir=archive_dir,
            ).normalize(),
        )

    def _read_archive_lines(self, archive_dir: str) -> List[Dict[str, Any]]:
        files = list(Path(archive_dir).rglob("*.jsonl"))
        self.assertEqual(len(files), 1)
        lines = [line for line in files[0].read_text(encoding="utf-8").splitlines() if line.strip()]
        return [json.loads(line) for line in lines]

    def test_agent_end_archives_and_skips_non_main_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self._make_runtime(archive_dir=tmp)
            runtime._retrieve_context = lambda **_: (_ for _ in ()).throw(AssertionError("retrieve should not run"))  # type: ignore[attr-defined]
            runtime._schedule_extraction_job = lambda **_: (_ for _ in ()).throw(AssertionError("schedule should not run"))  # type: ignore[attr-defined]

            payload = runtime.openclaw_agent_end_api(
                body={
                    "user": "u-test",
                    "session_id": "sess-side",
                    "turn_type": "side",
                    "success": True,
                    "messages": [
                        {"role": "user", "content": "Need a tool call."},
                        {"role": "assistant", "content": "Calling tool."},
                    ],
                },
                headers={},
            )

            self.assertEqual(payload["extraction"]["status"], "skipped")
            self.assertEqual(payload["extraction"]["reason"], "turn_type_side")
            archived = self._read_archive_lines(tmp)
            self.assertEqual(archived[0]["metadata"]["turn_type"], "side")
            self.assertEqual(archived[0]["metadata"]["session_id"], "sess-side")

    def test_agent_end_schedules_main_turn_when_proxy_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self._make_runtime(archive_dir=tmp)
            runtime._retrieve_context = lambda **_: {"hits": []}  # type: ignore[attr-defined]
            scheduled: List[Dict[str, Any]] = []

            def _schedule(**kwargs: Any) -> str:
                scheduled.append(dict(kwargs))
                return "job-1"

            runtime._schedule_extraction_job = _schedule  # type: ignore[assignment]

            payload = runtime.openclaw_agent_end_api(
                body={
                    "user": "u-test",
                    "session_id": "sess-main",
                    "turn_type": "main",
                    "success": True,
                    "messages": [
                        {"role": "user", "content": "Write a report."},
                        {"role": "assistant", "content": "Draft report."},
                    ],
                },
                headers={},
            )

            self.assertEqual(payload["extraction"]["status"], "scheduled")
            self.assertEqual(len(scheduled), 1)
            self.assertEqual(scheduled[0]["trigger"], "openclaw_agent_end")
            archived = self._read_archive_lines(tmp)
            self.assertEqual(archived[0]["metadata"]["turn_type"], "main")

    def test_agent_end_falls_back_to_extraction_when_main_turn_enabled_but_target_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self._make_runtime(
                archive_dir=tmp,
                main_turn_enabled=True,
                target_base_url="",
            )
            runtime._retrieve_context = lambda **_: {"hits": []}  # type: ignore[attr-defined]
            scheduled: List[Dict[str, Any]] = []

            def _schedule(**kwargs: Any) -> str:
                scheduled.append(dict(kwargs))
                return "job-fallback"

            runtime._schedule_extraction_job = _schedule  # type: ignore[assignment]

            payload = runtime.openclaw_agent_end_api(
                body={
                    "user": "u-test",
                    "session_id": "sess-fallback",
                    "turn_type": "main",
                    "success": True,
                    "messages": [
                        {"role": "user", "content": "Write a report."},
                        {"role": "assistant", "content": "Draft report."},
                    ],
                },
                headers={},
            )

            self.assertEqual(payload["extraction"]["status"], "scheduled")
            self.assertEqual(len(scheduled), 1)

    def test_agent_end_only_archives_when_main_turn_proxy_is_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self._make_runtime(
                archive_dir=tmp,
                main_turn_enabled=True,
                target_base_url="http://127.0.0.1:8000/v1",
            )
            runtime._retrieve_context = lambda **_: (_ for _ in ()).throw(AssertionError("retrieve should not run"))  # type: ignore[attr-defined]
            runtime._schedule_extraction_job = lambda **_: (_ for _ in ()).throw(AssertionError("schedule should not run"))  # type: ignore[attr-defined]

            payload = runtime.openclaw_agent_end_api(
                body={
                    "user": "u-test",
                    "session_id": "sess-proxy",
                    "turn_type": "main",
                    "success": True,
                    "messages": [
                        {"role": "user", "content": "Do the task."},
                        {"role": "assistant", "content": "Done."},
                    ],
                },
                headers={},
            )

            self.assertEqual(payload["extraction"]["status"], "skipped")
            self.assertEqual(payload["extraction"]["reason"], "main_turn_proxy_enabled")
            archived = self._read_archive_lines(tmp)
            self.assertEqual(archived[0]["metadata"]["source"], "openclaw_agent_end")


if __name__ == "__main__":
    unittest.main()
