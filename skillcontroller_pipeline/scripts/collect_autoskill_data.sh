python -m skillcontroller_pipeline.scripts.collect_autoskill_data \
    --input data/wildchat_1000.jsonl \
    --output_dir data/autoskill_transitions \
    --num_runs 1 \
    --llm_model deepseek-chat \
    --llm_url https://api.qingyuntop.top/v1 \
    --llm_api_key sk-DISQMJtpvWPwvub7Z4xC2IFHyzNt4gEwRB1dJ5fBzkt92wFY \
    --embeddings_provider hashing