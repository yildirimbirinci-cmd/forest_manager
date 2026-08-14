# Stage 4O.2 - SmolVLM Processor Metadata Compatibility

Observed target runtime:

- Python 3.11.9
- Torch 2.12.1+cpu
- Transformers 5.12.1
- Pillow 12.3.0
- SmolVLM model/config/processor files are present
- model architecture: Idefics3ForConditionalGeneration
- model type: idefics3

Root cause of the load failure:

The pinned model snapshot's processor metadata predates the stricter current
AutoProcessor lookup and does not expose the required image processor class.

The local compatibility fix adds, only when missing:

    preprocessor_config.json:
        image_processor_type = Idefics3ImageProcessor
        processor_class = Idefics3Processor

    processor_config.json:
        processor_class = Idefics3Processor

Model weights are not modified.

No network access is used.

## Apply metadata compatibility

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.smolvlm_stage4o2_processor_fix

Expected:

    Stage 4O.2 processor metadata compatibility passed.

Then run the real local inference again:

    python -m forest_manager.app.local_vision_stage4k "C:\Users\yildi\Desktop\ref\ref01.png"
