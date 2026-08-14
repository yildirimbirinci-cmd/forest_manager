# Stage 4M - Local Vision Hardware and Bundle Readiness

This stage does not download anything and does not use the internet.

It measures the workstation and reports:

- CPU / platform
- total RAM
- free disk space
- Torch
- Transformers
- Pillow
- CUDA availability
- NVIDIA GPU name
- GPU VRAM
- local Qwen model manifest/config/weights/processor state

It also aligns the Qwen backend with the supported Transformers loading pattern:

    device_map="auto"
    local_files_only=True
    trust_remote_code=False

## Run

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.local_vision_stage4m_readiness

Send the complete output back before model weights are installed. The hardware
profile determines how the final bundled model should be packaged and loaded.

No network access is performed by this command.
