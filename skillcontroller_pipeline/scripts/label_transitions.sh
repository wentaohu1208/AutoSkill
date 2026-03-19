cd /data/hwt/AutoSkill

# pip install skillnet-ai（如果还没装）
python -m skillcontroller_pipeline.scripts.label_transitions \
    --input_dir data/autoskill_transitions \
    --output_dir data/labeled_transitions \
    --api_key sk-DISQMJtpvWPwvub7Z4xC2IFHyzNt4gEwRB1dJ5fBzkt92wFY \
    --base_url https://api.qingyuntop.top/v1 \
    --model deepseek-chat \
    --similarity_threshold 0.7