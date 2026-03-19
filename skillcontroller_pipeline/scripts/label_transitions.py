"""Label collected transitions using SkillNet quality evaluation.

Reads transition JSONL files, evaluates each candidate skill with SkillNet,
and labels transitions as positive/negative based on skill quality + decision.

This is "方式 A: 后置评估" — runs after all transitions are collected.

Usage:
    python -m skillcontroller_pipeline.scripts.label_transitions \
        --input_dir data/autoskill_transitions \
        --output_dir data/labeled_transitions \
        --api_key <key> \
        --base_url https://api.qingyuntop.top/v1 \
        --model deepseek-chat \
        --similarity_threshold 0.7
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_transitions(input_dir: str) -> List[Dict[str, Any]]:
    """Load all transition JSONL files from input directory."""
    transitions = []
    input_path = Path(input_dir)

    for jsonl_file in sorted(input_path.glob("transitions_run*.jsonl")):
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    transitions.append(json.loads(line))
        logger.info(f"Loaded {len(transitions)} transitions from {jsonl_file.name}")

    return transitions


def save_transitions(transitions: List[Dict[str, Any]], output_path: str) -> None:
    """Save labeled transitions to JSONL."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for t in transitions:
            f.write(json.dumps(t, ensure_ascii=False, default=str) + "\n")
    logger.info(f"Saved {len(transitions)} labeled transitions to {output_path}")


def main(args: argparse.Namespace) -> None:
    """Run post-hoc labeling."""

    # 1. Load transitions
    transitions = load_transitions(args.input_dir)
    if not transitions:
        logger.error("No transitions found!")
        return

    logger.info(f"Total transitions: {len(transitions)}")

    # 2. Initialize SkillNet evaluator
    # pip install skillnet-ai
    from skillnet_ai.evaluator import SkillEvaluator, EvaluatorConfig

    config = EvaluatorConfig(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        run_scripts=False,
        cache_dir=args.cache_dir,
    )
    evaluator = SkillEvaluator(config)

    # 3. Label transitions
    from skillcontroller_pipeline.skill_quality_gate import label_all_transitions

    labeled = label_all_transitions(
        transitions=transitions,
        evaluator=evaluator,
        similarity_threshold=args.similarity_threshold,
        cache_dir=args.cache_dir,
    )

    # 4. Statistics
    stats = {}
    for t in labeled:
        label = t.get("label", "unknown")
        stats[label] = stats.get(label, 0) + 1

    logger.info("=" * 60)
    logger.info("LABELING RESULTS")
    logger.info("=" * 60)
    for label, count in sorted(stats.items()):
        pct = count / len(labeled) * 100
        logger.info(f"  {label}: {count} ({pct:.1f}%)")

    # 5. Save all labeled transitions
    output_all = Path(args.output_dir) / "all_labeled.jsonl"
    save_transitions(labeled, str(output_all))

    # 6. Save positive-only (for SFT)
    positive = [t for t in labeled if t.get("label") == "positive"]
    output_positive = Path(args.output_dir) / "sft_positive.jsonl"
    save_transitions(positive, str(output_positive))

    # 7. Save negative-only (for analysis or DPO)
    negative = [t for t in labeled if t.get("label") == "negative"]
    output_negative = Path(args.output_dir) / "sft_negative.jsonl"
    save_transitions(negative, str(output_negative))

    logger.info(f"\nSFT positive samples: {len(positive)}")
    logger.info(f"Negative samples: {len(negative)}")
    logger.info(f"Output dir: {args.output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Label transitions with SkillNet quality evaluation")
    parser.add_argument("--input_dir", type=str, required=True, help="Directory with transition JSONL files")
    parser.add_argument("--output_dir", type=str, default="data/labeled_transitions", help="Output directory")
    parser.add_argument("--api_key", type=str, required=True, help="LLM API key for SkillNet evaluate")
    parser.add_argument("--base_url", type=str, default="https://api.qingyuntop.top/v1", help="LLM API base URL")
    parser.add_argument("--model", type=str, default="deepseek-chat", help="LLM model for evaluation")
    parser.add_argument("--similarity_threshold", type=float, default=0.7, help="Threshold for discard labeling")
    parser.add_argument("--cache_dir", type=str, default="/tmp/skillnet_eval_cache", help="Temp dir for SKILL.md")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args)
