"""Download WildChat subset and convert to OpenAI-format JSONL.

Usage:
    python -m skillcontroller_pipeline.scripts.prepare_wildchat \
        --num_conversations 2000 \
        --output data/wildchat_2000.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)


def main(args: argparse.Namespace) -> None:
    """Download and convert WildChat data."""
    from datasets import load_dataset

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Download WildChat subset
    logger.info(f"Loading WildChat (first {args.num_conversations} conversations)...")
    ds = load_dataset(
        "allenai/WildChat-1M",
        split=f"train[:{args.num_conversations}]",
        cache_dir=args.cache_dir,
    )
    logger.info(f"Loaded {len(ds)} conversations")

    # Convert to OpenAI format and save
    count = 0
    skipped = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for row in ds:
            messages = row.get("conversation", [])
            if not messages or len(messages) < 2:
                skipped += 1
                continue

            # Filter: only keep conversations with user feedback/constraints
            # (these are more likely to produce meaningful skills)
            has_multi_turn = len(messages) >= 4
            has_user_correction = any(
                m.get("role") == "user" and i > 1
                for i, m in enumerate(messages)
            )

            if not args.no_filter and not (has_multi_turn or has_user_correction):
                skipped += 1
                continue

            record = {"messages": messages}
            if row.get("model"):
                record["model"] = row["model"]
            if row.get("language"):
                record["language"] = row["language"]

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    logger.info(f"Saved {count} conversations to {output_path} (skipped {skipped})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare WildChat data for AutoSkill")
    parser.add_argument("--num_conversations", type=int, default=2000, help="Number of conversations to download")
    parser.add_argument("--output", type=str, default="data/wildchat_2000.jsonl", help="Output JSONL path")
    parser.add_argument("--no_filter", action="store_true", help="Don't filter single-turn conversations")
    parser.add_argument("--cache_dir", type=str, default="/data/hwt/hf_data", help="HuggingFace cache directory")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args)
