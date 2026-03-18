"""Collect Controller training data by running AutoSkill on conversation data.

Feeds conversations into InstrumentedAutoSkill, recording every
maintenance decision (add/merge/discard) as a transition.

Supports multiple shuffle runs to increase state diversity.

Usage:
    python -m skillcontroller_pipeline.scripts.collect_autoskill_data \
        --input data/wildchat_2000.jsonl \
        --output_dir data/autoskill_transitions \
        --user_id u1 \
        --num_runs 3 \
        --shuffle \
        --llm_provider generic \
        --embeddings_provider generic
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import shutil
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_conversations(input_path: str) -> List[Dict[str, Any]]:
    """Load OpenAI-format conversations from JSONL."""
    conversations = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                conversations.append(json.loads(line))
    logger.info(f"Loaded {len(conversations)} conversations from {input_path}")
    return conversations


def build_sdk(args: argparse.Namespace, store_dir: str) -> "AutoSkill":
    """Build AutoSkill SDK instance."""
    from autoskill import AutoSkill, AutoSkillConfig

    config_dict: Dict[str, Any] = {
        "store": {"provider": "local", "path": store_dir},
    }

    # LLM config
    if args.llm_provider == "generic":
        config_dict["llm"] = {
            "provider": "generic",
            "model": args.llm_model or os.environ.get("AUTOSKILL_GENERIC_LLM_MODEL", "deepseek-chat"),
            "url": args.llm_url or os.environ.get("AUTOSKILL_GENERIC_LLM_URL", ""),
            "api_key": args.llm_api_key or os.environ.get("AUTOSKILL_GENERIC_API_KEY", ""),
        }
    else:
        config_dict["llm"] = {"provider": args.llm_provider}

    if args.llm_model:
        config_dict["llm"]["model"] = args.llm_model

    # Embeddings config
    if args.embeddings_provider == "generic":
        config_dict["embeddings"] = {
            "provider": "generic",
            "model": os.environ.get("AUTOSKILL_GENERIC_EMBED_MODEL", "text-embedding-v4"),
        }
    elif args.embeddings_provider == "hashing":
        config_dict["embeddings"] = {"provider": "hashing", "dims": 256}
    else:
        config_dict["embeddings"] = {"provider": args.embeddings_provider}

    if args.embeddings_model:
        config_dict["embeddings"]["model"] = args.embeddings_model

    sdk = AutoSkill(AutoSkillConfig.from_dict(config_dict))
    return sdk


def run_single_pass(
    conversations: List[Dict[str, Any]],
    sdk: "AutoSkill",
    user_id: str,
    run_id: int,
    output_dir: Path,
) -> int:
    """Run one pass of conversations through InstrumentedAutoSkill."""
    from skillcontroller_pipeline.instrumented_sdk import InstrumentedAutoSkill

    save_path = output_dir / f"transitions_run{run_id}.jsonl"
    instrumented = InstrumentedAutoSkill(sdk, save_path=save_path)

    # Clear skill bank for this run
    instrumented.reset_bank(user_id)
    logger.info(f"Run {run_id}: Processing {len(conversations)} conversations...")

    processed = 0
    failed = 0

    for idx, conv in enumerate(conversations):
        messages = conv.get("messages", [])
        if not messages:
            continue

        try:
            instrumented.ingest(
                messages=messages,
                user_id=user_id,
                metadata={
                    "channel": "skillcontroller_data_collection",
                    "run_id": run_id,
                    "conversation_index": idx,
                },
            )
            processed += 1
        except Exception as e:
            failed += 1
            if failed <= 5:
                logger.warning(f"Run {run_id}, conv {idx}: {e}")
            elif failed == 6:
                logger.warning("Suppressing further error logs...")

        if (idx + 1) % 100 == 0:
            logger.info(f"Run {run_id}: {idx + 1}/{len(conversations)} processed, {len(instrumented.records)} transitions")

    # Save transitions
    instrumented.save()
    summary = instrumented.summary()
    logger.info(
        f"Run {run_id} complete: {processed} processed, {failed} failed, "
        f"{summary['total_transitions']} transitions, "
        f"actions={summary['action_counts']}"
    )

    return summary["total_transitions"]


def main(args: argparse.Namespace) -> None:
    """Main data collection loop."""
    conversations = load_conversations(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    total_transitions = 0

    for run_id in range(args.num_runs):
        logger.info(f"{'='*60}")
        logger.info(f"Starting Run {run_id}/{args.num_runs}")
        logger.info(f"{'='*60}")

        # Shuffle conversations for diversity
        run_conversations = list(conversations)
        if args.shuffle:
            random.seed(args.seed + run_id)
            random.shuffle(run_conversations)

        # Use separate store dir per run to avoid cross-contamination
        store_dir = str(output_dir / f"SkillBank_run{run_id}")
        if os.path.exists(store_dir):
            shutil.rmtree(store_dir)

        sdk = build_sdk(args, store_dir)

        n = run_single_pass(
            conversations=run_conversations,
            sdk=sdk,
            user_id=args.user_id,
            run_id=run_id,
            output_dir=output_dir,
        )
        total_transitions += n

    logger.info(f"{'='*60}")
    logger.info(f"All runs complete. Total transitions: {total_transitions}")
    logger.info(f"Output dir: {output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect AutoSkill training data")
    parser.add_argument("--input", type=str, required=True, help="Input JSONL path")
    parser.add_argument("--output_dir", type=str, default="data/autoskill_transitions", help="Output directory")
    parser.add_argument("--user_id", type=str, default="u1", help="User ID")
    parser.add_argument("--num_runs", type=int, default=1, help="Number of shuffle runs")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle conversations each run")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    # LLM config
    parser.add_argument("--llm_provider", type=str, default="generic", help="LLM provider")
    parser.add_argument("--llm_model", type=str, default="deepseek-chat", help="LLM model name")
    parser.add_argument("--llm_url", type=str, default=None, help="LLM API URL (for generic provider)")
    parser.add_argument("--llm_api_key", type=str, default=None, help="LLM API key (for generic provider)")
    parser.add_argument("--embeddings_provider", type=str, default="hashing", help="Embeddings provider")
    parser.add_argument("--embeddings_model", type=str, default=None, help="Embeddings model name")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args)
