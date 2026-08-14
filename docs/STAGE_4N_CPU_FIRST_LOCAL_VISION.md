# Stage 4N - CPU-First Local Vision Model

Hardware profile from the target workstation:

- 32 logical CPU threads
- about 64 GB RAM
- about 1.2 TB free disk
- Torch installed
- Transformers installed
- Pillow installed
- CUDA unavailable to the current Torch runtime

Because CUDA is not currently available, Forest Manager changes its default local
vision model from Qwen2.5-VL-3B-Instruct to:

    HuggingFaceTB/SmolVLM-500M-Instruct

Product model directory:

    models/vision/smolvlm-500m-instruct

Runtime rules remain unchanged:

- no API key
- no runtime network
- no cloud fallback
- local_files_only=True
- trust_remote_code=False
- HF_HUB_OFFLINE=1
- TRANSFORMERS_OFFLINE=1

Device behavior:

- CUDA if a compatible local Torch runtime is available
- otherwise CPU
- CPU dtype defaults to float32 for compatibility

## Readiness

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.local_vision_stage4n_readiness

Until model files are placed in the model directory, NOT READY is the correct result.

## Import an already-local model copy

    python tools/import_local_smolvlm_model.py "D:\Models\SmolVLM-500M-Instruct"

The importer does not download anything.

The final application installer should bundle the approved model files directly,
so end users do not need Hugging Face or internet access.
