"""Convert raw transitions to Controller training data.

Supports two output formats:
- MLP format: numerical features + action label
- LM format: text prompt + JSON completion (pure 3-class decision)

Prompt design:
- Skill bank: name + description per skill (one line each)
- Candidate: full info (name, description, instructions, triggers, tags, confidence)
- Optional context: similar_hits (may be absent in other frameworks)
- Training-time dropout: randomly drop optional fields for cross-framework generality
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from .feature_extractor import FeatureExtractor

logger = logging.getLogger(__name__)

# Optional fields that may not exist in other frameworks
OPTIONAL_FIELDS = ["instructions", "triggers", "tags", "confidence"]
DEFAULT_DROPOUT_RATE = 0.3


class DataConverter:
    """Convert InstrumentedAutoSkill transitions to training data."""

    def __init__(self, dropout_rate: float = DEFAULT_DROPOUT_RATE, seed: int = 42) -> None:
        self.extractor = FeatureExtractor()
        self.dropout_rate = dropout_rate
        self.rng = random.Random(seed)

    def convert_all(
        self,
        transitions: List[Dict[str, Any]],
        output_dir: str | Path,
        formats: List[str] = ("mlp", "lm"),
    ) -> Dict[str, Path]:
        """Convert all transitions and save to files."""
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
        """Convert to MLP training format: features + action."""
        samples = []
        history: List[Dict[str, Any]] = []

        for record in transitions:
            features = self.extractor.extract(record, history)

            sample = {
                "step": record["step"],
                "features": features,
                "action": record["action"],
                "action_id": {"add": 0, "merge": 1, "discard": 2}.get(record["action"], -1),
                "outcome": {
                    "delta_performance": record.get("delta_performance"),
                    "delta_token_usage": record.get("delta_token_usage"),
                },
            }
            samples.append(sample)
            history.append(record)

        return samples

    def _to_lm_format(self, transitions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert to LM training format: text prompt + JSON completion."""
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

    def _build_prompt(self, record: Dict[str, Any]) -> str:
        """Build text prompt from transition record.

        Structure:
        1. Skill Bank: name + description per skill
        2. Candidate: full info (with optional field dropout)
        3. Optional Context: similar_hits
        """
        bank = record.get("skill_bank_before", [])
        candidate = record.get("candidate", {})
        similar = record.get("similar_hits", [])

        # --- 1. Skill Bank: name + description ---
        bank_lines = []
        for i, s in enumerate(bank, 1):
            desc = s.get("description", "")
            bank_lines.append(f"  [{i}] {s['name']}: {desc}")
        bank_text = "\n".join(bank_lines) if bank_lines else "  (empty)"

        # --- 2. Candidate: full info with dropout ---
        # Required fields (Agent Skills standard: name, description, instructions)
        candidate_lines = [
            f"  Name: {candidate.get('name', '')}",
            f"  Description: {candidate.get('description', '')}",
            f"  Instructions: {candidate.get('instructions', '')}",
        ]

        # Optional fields — randomly dropout for cross-framework generality

        triggers = candidate.get("triggers", [])
        if triggers and self.rng.random() > self.dropout_rate:
            candidate_lines.append(f"  Triggers: {', '.join(triggers)}")

        tags = candidate.get("tags", [])
        if tags and self.rng.random() > self.dropout_rate:
            candidate_lines.append(f"  Tags: {', '.join(tags)}")

        confidence = candidate.get("confidence")
        if confidence is not None and self.rng.random() > self.dropout_rate:
            candidate_lines.append(f"  Confidence: {confidence:.2f}")

        candidate_text = "\n".join(candidate_lines)

        # --- 3. Optional Context: similar_hits ---
        optional_lines = []
        if similar and self.rng.random() > self.dropout_rate:
            similar_entries = []
            for h in similar[:3]:
                similar_entries.append(f"  {h['skill_name']} (score={h['score']:.2f}, v{h['skill_version']})")
            optional_lines.append("Optional Context:")
            optional_lines.append("  Most Similar Existing Skills:")
            optional_lines.extend([f"  {e}" for e in similar_entries])

        optional_text = "\n".join(optional_lines) if optional_lines else ""

        # --- Assemble prompt ---
        parts = [
            f"Current Skill Bank ({len(bank)} skills):",
            bank_text,
            "",
            "Candidate Skill:",
            candidate_text,
        ]

        if optional_text:
            parts.append("")
            parts.append(optional_text)

        parts.append("")
        parts.append("Decide: add, merge, or discard?")

        return "\n".join(parts)

    @staticmethod
    def _build_completion(record: Dict[str, Any]) -> str:
        """Build JSON completion — pure 3-class decision, no skill content."""
        action = record["action"]
        return json.dumps({"operation": action}, ensure_ascii=False)

    @staticmethod
    def _save_jsonl(data: List[Dict[str, Any]], path: Path) -> None:
        """Save list of dicts as JSONL."""
        with open(path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
