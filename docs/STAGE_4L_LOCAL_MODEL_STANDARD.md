# Stage 4L - Local Model Standard

Forest Manager now has one default local vision model target:

    Qwen/Qwen2.5-VL-3B-Instruct

Runtime location:

    models/vision/qwen2.5-vl-3b-instruct

Runtime rules:

- Offline only.
- No API key.
- No cloud fallback.
- `HF_HUB_OFFLINE=1`.
- `TRANSFORMERS_OFFLINE=1`.
- `local_files_only=True`.
- `trust_remote_code=False`.
- Reference images remain local.

The repository/package does not include the large model weights yet.

## Check readiness

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.local_model_stage4l_readiness

Until the model weights are present, the expected result is:

    Stage 4L model readiness: NOT READY

## Import an existing local copy

If the complete model already exists somewhere on the workstation:

    python tools/import_local_qwen_model.py "D:\Models\Qwen2.5-VL-3B-Instruct"

The importer only copies local files. It has no download function.

The final Forest Manager installer can later bundle this model directly so the
end user never needs Hugging Face, an API key, or an internet connection.
