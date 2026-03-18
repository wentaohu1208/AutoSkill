"""Convert raw transitions to Controller training data.

Supports two output formats:
- MLP format: numerical features + action label
- LM format: text prompt + JSON completion
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .feature_extractor import FeatureExtractor

logger = logging.getLogger(__name__)


class DataConverter:
    """Convert InstrumentedAutoSkill transitions to training data."""

    def __init__(self) -> None:
        self.extractor = FeatureExtractor()

    def convert_all(
        self,
        transitions: List[Dict[str, Any]],
        output_dir: str | Path,
        formats: List[str] = ("mlp", "lm"),
    ) -> Dict[str, Path]:
        """Convert all transitions and save to files.

        Args:
            transitions: List of transition records from InstrumentedAutoSkill.
            output_dir: Directory to save output files.
            formats: Which formats to generate ("mlp", "lm", or both).

        Returns:
            Mapping from format name to output file path.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        results = {}

        if "mlp" in formats:
            mlp_data = self._to_mlp_format(transitions)
            mlp_path = output_dir / "training_data_mlp.jsonl"
            self._save_jsonl(mlp_data, mlp_path)
            results["mlp"] = mlp_path
            logger.info(f"Saved {len(mlp_data)} MLP samples to {mlp_path}")

        if "lm" in formats:
            lm_data = self._to_lm_format(transitions)
            lm_path = output_dir / "training_data_lm.jsonl"
            self._save_jsonl(lm_data, lm_path)
            results["lm"] = lm_path
            logger.info(f"Saved {len(lm_data)} LM samples to {lm_path}")

        return results

    def _to_mlp_format(self, transitions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert to MLP training format: features + action.

        Each sample:
        {
            "features": {"top1_similarity": 0.92, ...},
            "action": "merge",
            "action_id": 1,
            "target_skill_id": "sk_001",
            "outcome": {"delta_performance": null}
        }
        """
        samples = []
        history: List[Dict[str, Any]] = []

        for record in transitions:
            features = self.extractor.extract(record, history)

            sample = {
                "step": record["step"],
                "features": features,
                "action": record["action"],
                "action_id": {"add": 0, "merge": 1, "discard": 2}.get(record["action"], -1),
                "target_skill_id": record.get("target_skill_id"),
                "outcome": {
                    "delta_performance": record.get("delta_performance"),
                    "delta_token_usage": record.get("delta_token_usage"),
                },
            }
            samples.append(sample)
            history.append(record)

        return samples

    def _to_lm_format(self, transitions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert to LM training format: text prompt + JSON completion.

        Each sample:
        {
            "prompt": "Current Skill Bank (15 nodes):\n...\nCandidate: ...",
            "completion": '{"operation": "merge", "target": "sk_001"}',
            "action": "merge",
            "outcome": {...}
        }
        """
        samples = []

        for record in transitions:
            prompt = self._build_prompt(record)
            completion = self._build_completion(record)

            sample = {
                "step": record["step"],
                "prompt": prompt,
                "completion": completion,
                "action": record["action"],
                "outcome": {
                    "delta_performance": record.get("delta_performance"),
                    "delta_token_usage": record.get("delta_token_usage"),
                },
            }
            samples.append(sample)

        return samples

    @staticmethod
    def _build_prompt(record: Dict[str, Any]) -> str:
        """Build text prompt from transition record."""
        bank = record.get("skill_bank_before", [])
        candidate = record.get("candidate", {})
        similar = record.get("similar_hits", [])

        # Skill bank summary
        bank_lines = []
        for s in bank:
            bank_lines.append(f"  [{s['id'][:8]}] {s['name']} (v{s['version']})")
        bank_text = "\n".join(bank_lines) if bank_lines else "  (empty)"

        # Similar hits
        similar_lines = []
        for h in similar[:3]:
            similar_lines.append(f"  {h['skill_name']} (score={h['score']:.2f}, v{h['skill_version']})")
        similar_text = "\n".join(similar_lines) if similar_lines else "  (none)"

        prompt = (
            f"Current Skill Bank ({len(bank)} skills):\n"
            f"{bank_text}\n\n"
            f"Candidate Skill:\n"
            f"  Name: {candidate.get('name', '')}\n"
            f"  Description: {candidate.get('description', '')[:200]}\n"
            f"  Confidence: {candidate.get('confidence', 0):.2f}\n"
            f"  Triggers: {', '.join(candidate.get('triggers', [])[:3])}\n\n"
            f"Most Similar Existing Skills:\n"
            f"{similar_text}\n\n"
            f"Decide: add, merge, or discard?"
        )
        return prompt

    @staticmethod
    def _build_completion(record: Dict[str, Any]) -> str:
        """Build JSON completion from transition record."""
        action = record["action"]
        target = record.get("target_skill_id")

        completion = {"operation": action}
        if target:
            completion["target_skill_id"] = target

        return json.dumps(completion, ensure_ascii=False)

    @staticmethod
    def _save_jsonl(data: List[Dict[str, Any]], path: Path) -> None:
        """Save list of dicts as JSONL."""
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
