"""Convert collected transitions to Controller training data.

Reads transition JSONL files from collect_autoskill_data.py output
and converts to MLP and/or LM training formats.

Usage:
    python -m skillcontroller_pipeline.scripts.convert_to_training_data \
        --input_dir data/autoskill_transitions \
        --output_dir data/training_data \
        --format both
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)


def load_all_transitions(input_dir: str) -> List[Dict[str, Any]]:
    """Load all transition JSONL files from input directory."""
    transitions = []
    input_path = Path(input_dir)

    for jsonl_file in sorted(input_path.glob("transitions_run*.jsonl")):
        run_transitions = []
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    run_transitions.append(json.loads(line))
        logger.info(f"Loaded {len(run_transitions)} transitions from {jsonl_file.name}")
        transitions.extend(run_transitions)

    logger.info(f"Total transitions loaded: {len(transitions)}")
    return transitions


def print_stats(transitions: List[Dict[str, Any]]) -> None:
    """Print statistics about the collected data."""
    action_counts: Dict[str, int] = {}
    for t in transitions:
        a = t.get("action", "unknown")
        action_counts[a] = action_counts.get(a, 0) + 1

    logger.info("=" * 50)
    logger.info("DATA STATISTICS")
    logger.info("=" * 50)
    logger.info(f"Total transitions: {len(transitions)}")
    for action, count in sorted(action_counts.items()):
        pct = count / len(transitions) * 100
        logger.info(f"  {action}: {count} ({pct:.1f}%)")

    # Bank size distribution
    bank_sizes = [t.get("bank_size_before", 0) for t in transitions]
    if bank_sizes:
        logger.info(f"Bank size: min={min(bank_sizes)}, max={max(bank_sizes)}, avg={sum(bank_sizes)/len(bank_sizes):.1f}")


def main(args: argparse.Namespace) -> None:
    """Convert transitions to training data."""
    from skillcontroller_pipeline.data_converter import DataConverter

    transitions = load_all_transitions(args.input_dir)
    if not transitions:
        logger.error("No transitions found!")
        return

    print_stats(transitions)

    formats = []
    if args.format in ("mlp", "both"):
        formats.append("mlp")
    if args.format in ("lm", "both"):
        formats.append("lm")

    converter = DataConverter()
    results = converter.convert_all(
        transitions=transitions,
        output_dir=args.output_dir,
        formats=formats,
    )

    logger.info("=" * 50)
    logger.info("OUTPUT FILES")
    logger.info("=" * 50)
    for fmt, path in results.items():
        # Count lines
        with open(path) as f:
            n = sum(1 for _ in f)
        logger.info(f"  {fmt}: {path} ({n} samples)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert transitions to training data")
    parser.add_argument("--input_dir", type=str, required=True, help="Directory with transition JSONL files")
    parser.add_argument("--output_dir", type=str, default="data/training_data", help="Output directory")
    parser.add_argument("--format", type=str, default="both", choices=["mlp", "lm", "both"], help="Output format")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args)
