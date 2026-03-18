python -m skillcontroller_pipeline.scripts.collect_autoskill_data \
    --input data/wildchat_sample.jsonl \
    --output_dir data/autoskill_transitions \
    --num_runs 1 \
    --llm_provider generic \
    --embeddings_provider hashing