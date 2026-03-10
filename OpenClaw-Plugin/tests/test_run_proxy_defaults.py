from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLUGIN_DIR = _REPO_ROOT / "OpenClaw-Plugin"
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from run_proxy import _resolve_agent_end_extract_enabled, build_parser  # noqa: E402


class RunProxyDefaultsTest(unittest.TestCase):
    def test_main_turn_extract_defaults_to_enabled(self) -> None:
        prev = os.environ.get("AUTOSKILL_OPENCLAW_MAIN_TURN_EXTRACT")
        try:
            os.environ.pop("AUTOSKILL_OPENCLAW_MAIN_TURN_EXTRACT", None)
            args = build_parser().parse_args([])
        finally:
            if prev is None:
                os.environ.pop("AUTOSKILL_OPENCLAW_MAIN_TURN_EXTRACT", None)
            else:
                os.environ["AUTOSKILL_OPENCLAW_MAIN_TURN_EXTRACT"] = prev
        self.assertEqual(str(args.openclaw_main_turn_extract), "1")

    def test_agent_end_defaults_to_disabled_when_main_turn_enabled(self) -> None:
        enabled = _resolve_agent_end_extract_enabled(
            main_turn_enabled=True,
            target_configured=True,
            raw_value="",
            explicit=False,
        )
        self.assertFalse(enabled)

    def test_agent_end_defaults_to_enabled_until_main_turn_target_is_configured(self) -> None:
        enabled = _resolve_agent_end_extract_enabled(
            main_turn_enabled=True,
            target_configured=False,
            raw_value="",
            explicit=False,
        )
        self.assertTrue(enabled)

    def test_agent_end_can_still_be_explicitly_enabled(self) -> None:
        enabled = _resolve_agent_end_extract_enabled(
            main_turn_enabled=True,
            target_configured=True,
            raw_value="1",
            explicit=True,
        )
        self.assertTrue(enabled)


if __name__ == "__main__":
    unittest.main()
