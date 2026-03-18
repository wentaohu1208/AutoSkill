"""Extract domain-agnostic features from AutoSkill transitions.

Converts raw transition records into numerical features
for training the Controller's Decision Model.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Action type encoding
ACTION_ENCODING = {"add": 0, "merge": 1, "discard": 2}


class FeatureExtractor:
    """Extract structured features from a transition record.

    Features are domain-agnostic: similarity scores, graph statistics,
    recent action patterns. No text content.
    """

    def extract(self, record: Dict[str, Any], history: List[Dict[str, Any]]) -> Dict[str, float]:
        """Extract features from a single transition record.

        Args:
            record: One transition from InstrumentedAutoSkill.
            history: Previous transitions (for computing trends).

        Returns:
            Feature dict with float values.
        """
        similar_hits = record.get("similar_hits", [])
        bank_before = record.get("skill_bank_before", [])
        candidate = record.get("candidate", {})

        # Similarity features
        top1_sim = similar_hits[0]["score"] if similar_hits else 0.0
        top2_sim = similar_hits[1]["score"] if len(similar_hits) >= 2 else 0.0
        top3_sim = similar_hits[2]["score"] if len(similar_hits) >= 3 else 0.0
        sim_gap = top1_sim - top2_sim

        # Graph size features
        bank_size = record.get("bank_size_before", 0)

        # Version features (how mature is the top match)
        top1_version = 0.0
        if similar_hits:
            version_str = similar_hits[0].get("skill_version", "0.1.0")
            top1_version = self._parse_patch_version(version_str)

        # Candidate features
        candidate_confidence = candidate.get("confidence", 0.0)
        candidate_trigger_count = len(candidate.get("triggers", []))
        candidate_tag_count = len(candidate.get("tags", []))
        candidate_desc_len = len(candidate.get("description", ""))
        candidate_instr_len = len(candidate.get("instructions", ""))

        # History features (recent actions pattern)
        recent_actions = self._get_recent_actions(history, window=5)
        recent_add_rate = recent_actions.count("add") / max(len(recent_actions), 1)
        recent_merge_rate = recent_actions.count("merge") / max(len(recent_actions), 1)
        recent_discard_rate = recent_actions.count("discard") / max(len(recent_actions), 1)

        steps_since_last_add = self._steps_since(history, "add")
        steps_since_last_merge = self._steps_since(history, "merge")
        steps_since_last_discard = self._steps_since(history, "discard")

        # Bank growth trend
        bank_growth = self._bank_growth_trend(history, window=5)

        return {
            # Similarity features (5)
            "top1_similarity": top1_sim,
            "top2_similarity": top2_sim,
            "top3_similarity": top3_sim,
            "sim_gap_1_2": sim_gap,
            "top1_version": top1_version,
            # Graph features (1)
            "bank_size": float(bank_size),
            # Candidate features (4)
            "candidate_confidence": candidate_confidence,
            "candidate_trigger_count": float(candidate_trigger_count),
            "candidate_tag_count": float(candidate_tag_count),
            "candidate_desc_len": float(min(candidate_desc_len, 1000)) / 1000.0,
            # History features (7)
            "recent_add_rate": recent_add_rate,
            "recent_merge_rate": recent_merge_rate,
            "recent_discard_rate": recent_discard_rate,
            "steps_since_last_add": float(min(steps_since_last_add, 20)),
            "steps_since_last_merge": float(min(steps_since_last_merge, 20)),
            "steps_since_last_discard": float(min(steps_since_last_discard, 20)),
            "bank_growth_trend": bank_growth,
        }

    @staticmethod
    def _parse_patch_version(version_str: str) -> float:
        """Extract patch number from version string like '0.1.8' → 8.0."""
        try:
            parts = str(version_str).split(".")
            return float(parts[-1]) if parts else 0.0
        except (ValueError, IndexError):
            return 0.0

    @staticmethod
    def _get_recent_actions(history: List[Dict[str, Any]], window: int = 5) -> List[str]:
        """Get last N actions from history."""
        recent = history[-window:] if history else []
        return [r.get("action", "") for r in recent]

    @staticmethod
    def _steps_since(history: List[Dict[str, Any]], action: str) -> int:
        """Steps since last occurrence of an action type."""
        for i, r in enumerate(reversed(history)):
            if r.get("action") == action:
                return i
        return len(history) + 1

    @staticmethod
    def _bank_growth_trend(history: List[Dict[str, Any]], window: int = 5) -> float:
        """Average bank size change over recent steps."""
        recent = history[-window:] if history else []
        if len(recent) < 2:
            return 0.0
        deltas = []
        for r in recent:
            delta = r.get("bank_size_after", 0) - r.get("bank_size_before", 0)
            deltas.append(delta)
        return sum(deltas) / len(deltas)

    @staticmethod
    def feature_names() -> List[str]:
        """Return ordered list of feature names."""
        return [
            "top1_similarity", "top2_similarity", "top3_similarity",
            "sim_gap_1_2", "top1_version",
            "bank_size",
            "candidate_confidence", "candidate_trigger_count",
            "candidate_tag_count", "candidate_desc_len",
            "recent_add_rate", "recent_merge_rate", "recent_discard_rate",
            "steps_since_last_add", "steps_since_last_merge",
            "steps_since_last_discard", "bank_growth_trend",
        ]

    @staticmethod
    def feature_dim() -> int:
        """Return number of features."""
        return 17
