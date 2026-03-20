export HF_ENDPOINT=https://hf-mirror.com;
cd /data/hwt/AutoSkill && \
python -m skillcontroller_pipeline.scripts.prepare_wildchat \
    --num_conversations 5000 \
    --output data/wildchat.jsonl \
    --language English \
    --cache_dir /data/hwt/hf_data \
    --min_turns 4