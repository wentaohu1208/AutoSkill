cd /data/hwt/AutoSkill;
python -m skillcontroller_pipeline.scripts.convert_to_training_data \
    --input_dir data/autoskill_transitions \
    --output_dir data/training_data \
    --format lm