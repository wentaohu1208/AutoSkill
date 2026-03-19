"""SkillNet-based quality evaluation for AutoSkill candidates.

Uses SkillNet's five-dimension evaluate() to assess candidate skill quality,
then combines with AutoSkill's decision and similarity score to label
transitions as positive (good decision) or negative (bad decision).

This implements "方式 A: 后置评估" — runs after all transitions are collected.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Quality levels
GOOD = "Good"
AVERAGE = "Average"
POOR = "Poor"

DIMENSIONS = ["safety", "completeness", "executability", "maintainability", "cost_awareness"]


def _check_high_quality(levels: Dict[str, str]) -> tuple[bool, str]:
    """Layered quality gate with priority.

    Layer 1 (Safety red line): Safety=Poor → reject
    Layer 2 (Usability): Completeness=Poor or Executability=Poor → reject
    Layer 3 (Engineering): Maintainability+Cost both Poor → reject

    Returns:
        (is_high_quality, reject_reason)
    """
    # Layer 1: Safety red line
    if levels.get("safety") == POOR:
        return False, "safety_poor"

    # Layer 2: Usability — agent must be able to understand and execute
    if levels.get("completeness") == POOR:
        return False, "completeness_poor"
    if levels.get("executability") == POOR:
        return False, "executability_poor"

    # Layer 3: Engineering quality — tolerate one Poor, reject both
    if levels.get("maintainability") == POOR and levels.get("cost_awareness") == POOR:
        return False, "maintainability_and_cost_both_poor"

    return True, ""


@dataclass
class QualityResult:
    """Result of SkillNet five-dimension evaluation."""

    levels: Dict[str, str]  # dimension -> "Good"/"Average"/"Poor"
    reasons: Dict[str, str]  # dimension -> reason text
    poor_count: int
    good_count: int
    is_high_quality: bool
    reject_reason: str  # why rejected, empty if high quality

    def to_dict(self) -> Dict[str, Any]:
        return {
            "levels": self.levels,
            "reasons": self.reasons,
            "poor_count": self.poor_count,
            "good_count": self.good_count,
            "is_high_quality": self.is_high_quality,
            "reject_reason": self.reject_reason,
        }


def _export_candidate_as_skill_md(candidate: Dict[str, Any], output_dir: str) -> str:
    """Export an AutoSkill candidate to a temporary SKILL.md directory.

    Args:
        candidate: Candidate dict from AutoSkill transition.
        output_dir: Directory to write SKILL.md into.

    Returns:
        Path to the skill directory.
    """
    os.makedirs(output_dir, exist_ok=True)

    name = candidate.get("name", "unnamed-skill")
    description = candidate.get("description", "")
    instructions = candidate.get("instructions", "")
    triggers = candidate.get("triggers", [])
    tags = candidate.get("tags", [])

    # Build SKILL.md in SkillNet format
    frontmatter = (
        f"---\n"
        f"name: {name}\n"
        f'description: "{description}"\n'
        f"---\n\n"
    )

    body = f"# {name}\n\n"
    if description:
        body += f"{description}\n\n"
    if instructions:
        body += f"## Instructions\n\n{instructions}\n\n"
    if triggers:
        body += "## Triggers\n\n"
        for t in triggers:
            body += f"- {t}\n"
        body += "\n"
    if tags:
        body += f"## Tags\n\n{', '.join(tags)}\n"

    skill_md_path = os.path.join(output_dir, "SKILL.md")
    with open(skill_md_path, "w", encoding="utf-8") as f:
        f.write(frontmatter + body)

    return output_dir


def evaluate_candidate(
    candidate: Dict[str, Any],
    evaluator: Any,
    cache_dir: str = "/tmp/skillnet_eval_cache",
) -> QualityResult:
    """Evaluate a single candidate skill using SkillNet.

    Args:
        candidate: Candidate dict from AutoSkill transition.
        evaluator: SkillEvaluator instance from skillnet_ai.
        cache_dir: Temp directory for exporting SKILL.md.

    Returns:
        QualityResult with five-dimension scores.
    """
    from skillnet_ai.evaluator import Skill

    # Export candidate to temp SKILL.md
    skill_name = candidate.get("name", "unnamed")
    tmp_dir = os.path.join(cache_dir, skill_name.replace("/", "_").replace(" ", "_"))

    try:
        _export_candidate_as_skill_md(candidate, tmp_dir)

        # Create SkillNet Skill object
        skill, err = Skill.from_path(tmp_dir, name=skill_name)
        if err or skill is None:
            logger.warning(f"Failed to create Skill from path: {err}")
            return QualityResult(
                levels={d: AVERAGE for d in DIMENSIONS},
                reasons={d: "evaluation_failed" for d in DIMENSIONS},
                poor_count=0,
                good_count=0,
                is_high_quality=True,  # 评估失败时不拦截
                reject_reason="",
            )

        # Run SkillNet evaluate
        result = evaluator.evaluate(skill)

        # Parse result
        levels = {}
        reasons = {}
        for dim in DIMENSIONS:
            dim_result = result.get(dim, {})
            if isinstance(dim_result, dict):
                levels[dim] = dim_result.get("level", AVERAGE)
                reasons[dim] = dim_result.get("reason", "")
            else:
                levels[dim] = AVERAGE
                reasons[dim] = ""

        poor_count = sum(1 for v in levels.values() if v == POOR)
        good_count = sum(1 for v in levels.values() if v == GOOD)
        is_hq, reject_reason = _check_high_quality(levels)

        return QualityResult(
            levels=levels,
            reasons=reasons,
            poor_count=poor_count,
            good_count=good_count,
            is_high_quality=is_hq,
            reject_reason=reject_reason,
        )

    except Exception as e:
        logger.warning(f"SkillNet evaluation failed for {skill_name}: {e}")
        return QualityResult(
            levels={d: AVERAGE for d in DIMENSIONS},
            reasons={d: f"error: {e}" for d in DIMENSIONS},
            poor_count=0,
            good_count=0,
            is_high_quality=True,  # 评估失败时不拦截
            reject_reason="",
        )

    finally:
        # Cleanup temp dir
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


def label_transition(
    transition: Dict[str, Any],
    quality: QualityResult,
    similarity_threshold: float = 0.7,
) -> str:
    """Label a transition as positive or negative based on skill quality and decision.

    Args:
        transition: One transition record from InstrumentedAutoSkill.
        quality: SkillNet evaluation result.
        similarity_threshold: Above this, discard of good skill is considered correct (dedup).

    Returns:
        "positive", "negative", or "ambiguous".
    """
    action = transition.get("action", "")
    similar_hits = transition.get("similar_hits", [])
    top1_similarity = similar_hits[0]["score"] if similar_hits else 0.0

    if not quality.is_high_quality:
        # Low quality skill
        if action in ("add", "merge"):
            return "negative"  # Added/merged garbage → bad decision
        elif action == "discard":
            return "positive"  # Discarded garbage → good decision
    else:
        # High quality skill
        if action in ("add", "merge"):
            return "positive"  # Added/merged good skill → good decision
        elif action == "discard":
            if top1_similarity > similarity_threshold:
                return "positive"  # Good skill but duplicate exists → correct dedup
            else:
                return "negative"  # Good skill, no duplicate, but discarded → bad decision

    return "ambiguous"


def label_all_transitions(
    transitions: List[Dict[str, Any]],
    evaluator: Any,
    similarity_threshold: float = 0.7,
    cache_dir: str = "/tmp/skillnet_eval_cache",
) -> List[Dict[str, Any]]:
    """Label all transitions with quality evaluation and decision labels.

    Args:
        transitions: List of transition records.
        evaluator: SkillEvaluator instance.
        similarity_threshold: For discard decision labeling.
        cache_dir: Temp directory for SKILL.md export.

    Returns:
        Same transitions with added 'skill_quality' and 'label' fields.
    """
    logger.info(f"Labeling {len(transitions)} transitions with SkillNet evaluate...")

    stats = {"positive": 0, "negative": 0, "ambiguous": 0, "eval_errors": 0}

    for i, t in enumerate(transitions):
        candidate = t.get("candidate", {})
        if not candidate or not candidate.get("name"):
            t["skill_quality"] = None
            t["label"] = "ambiguous"
            stats["ambiguous"] += 1
            continue

        # Evaluate
        quality = evaluate_candidate(candidate, evaluator, cache_dir=cache_dir)
        t["skill_quality"] = quality.to_dict()

        # Label
        label = label_transition(t, quality, similarity_threshold=similarity_threshold)
        t["label"] = label
        stats[label] += 1

        if (i + 1) % 1 == 0:
            logger.info(f"  Labeled {i+1}/{len(transitions)}: {stats}")

    logger.info(f"Labeling complete: {stats}")
    return transitions
