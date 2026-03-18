"""Instrumented AutoSkill SDK that records every maintenance decision.

Wraps AutoSkill.ingest() to capture (skill_bank_state, candidate, action, outcome)
transitions for training the SkillController.
"""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from autoskill import AutoSkill
from autoskill.models import Skill, SkillHit

logger = logging.getLogger(__name__)


def _skill_to_dict(skill: Skill) -> Dict[str, Any]:
    """Convert Skill to serializable dict, dropping heavy fields."""
    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "version": skill.version,
        "tags": list(skill.tags or []),
        "triggers": list(skill.triggers or []),
        "status": str(skill.status.value) if skill.status else "active",
        "created_at": skill.created_at,
        "updated_at": skill.updated_at,
    }


def _hit_to_dict(hit: SkillHit) -> Dict[str, Any]:
    """Convert SkillHit to serializable dict."""
    return {
        "skill_id": hit.skill.id,
        "skill_name": hit.skill.name,
        "skill_version": hit.skill.version,
        "score": float(hit.score),
    }


class InstrumentedAutoSkill:
    """Wraps AutoSkill SDK to record every maintenance decision as a transition.

    Args:
        sdk: Initialized AutoSkill instance.
        save_path: Path to save transition records (jsonl).
    """

    def __init__(self, sdk: AutoSkill, save_path: str | Path) -> None:
        self.sdk = sdk
        self.save_path = Path(save_path)
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        self.records: List[Dict[str, Any]] = []
        self._step = 0

        # Monkey-patch _upsert_candidate
        self._maintainer = sdk.maintainer
        self._store = self._maintainer._store
        self._original_upsert = self._maintainer._upsert_candidate
        self._maintainer._upsert_candidate = self._instrumented_upsert

    def _instrumented_upsert(self, cand, *, user_id: str, metadata: Optional[Dict] = None) -> Optional[Skill]:
        """Wrapped _upsert_candidate that records transitions."""
        # 1. Before: snapshot skill bank
        before_skills = self._store.list(user_id=user_id)

        # 2. Before: find similar skills for features
        query_text = f"{getattr(cand, 'name', '')} {getattr(cand, 'description', '')}"
        try:
            similar_hits = self._store.search(
                user_id=user_id,
                query=query_text,
                limit=5,
            )
        except Exception:
            similar_hits = []

        # 3. Execute original decision
        result = self._original_upsert(cand, user_id=user_id, metadata=metadata)

        # 4. Determine action type
        if result is None:
            action = "discard"
        elif result.version == "0.1.0" and result.created_at == result.updated_at:
            action = "add"
        else:
            action = "merge"

        # 5. After: snapshot skill bank
        after_skills = self._store.list(user_id=user_id)

        # 6. Record transition
        record = {
            "step": self._step,
            "user_id": user_id,
            "skill_bank_before": [_skill_to_dict(s) for s in before_skills],
            "candidate": {
                "name": getattr(cand, "name", ""),
                "description": getattr(cand, "description", ""),
                "instructions": getattr(cand, "instructions", "")[:500],
                "triggers": list(getattr(cand, "triggers", []) or []),
                "tags": list(getattr(cand, "tags", []) or []),
                "confidence": float(getattr(cand, "confidence", 0.0) or 0.0),
            },
            "similar_hits": [_hit_to_dict(h) for h in similar_hits],
            "action": action,
            "target_skill_id": result.id if result else None,
            "target_skill_version": result.version if result else None,
            "skill_bank_after": [_skill_to_dict(s) for s in after_skills],
            "bank_size_before": len(before_skills),
            "bank_size_after": len(after_skills),
        }

        self.records.append(record)
        self._step += 1

        logger.info(
            f"[Step {record['step']}] action={action}, "
            f"candidate={record['candidate']['name'][:40]}, "
            f"bank: {record['bank_size_before']}→{record['bank_size_after']}"
        )

        return result

    def ingest(self, **kwargs) -> List[Skill]:
        """Pass-through to sdk.ingest() (which now uses instrumented _upsert_candidate)."""
        return self.sdk.ingest(**kwargs)

    def save(self) -> Path:
        """Save all recorded transitions to jsonl."""
        with open(self.save_path, "w", encoding="utf-8") as f:
            for record in self.records:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        logger.info(f"Saved {len(self.records)} transitions to {self.save_path}")
        return self.save_path

    def reset_bank(self, user_id: str) -> None:
        """Clear all skills for a user (for multi-run shuffle experiments)."""
        skills = self._store.list(user_id=user_id)
        for skill in skills:
            try:
                self._store.delete(skill.id)
            except Exception as e:
                logger.warning(f"Failed to delete skill {skill.id}: {e}")
        logger.info(f"Cleared {len(skills)} skills for user {user_id}")

    def summary(self) -> Dict[str, Any]:
        """Summary statistics of collected data."""
        total = len(self.records)
        actions = {}
        for r in self.records:
            a = r["action"]
            actions[a] = actions.get(a, 0) + 1

        return {
            "total_transitions": total,
            "action_counts": actions,
            "final_bank_size": self.records[-1]["bank_size_after"] if self.records else 0,
        }
