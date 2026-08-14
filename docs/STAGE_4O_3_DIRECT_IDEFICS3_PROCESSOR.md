# Stage 4O.3 - Direct Idefics3 Processor Construction

Observed issue:
Transformers 5.12.1 still rejects the pinned SmolVLM snapshot through
AutoProcessor even after the local metadata contains the expected processor
fields.

This update removes AutoProcessor from the runtime path.

The local processor is now built explicitly from:

    Idefics3ImageProcessor.from_pretrained(local model dir)
    AutoTokenizer.from_pretrained(local model dir)
    Idefics3Processor(image_processor=..., tokenizer=..., image_seq_len=...)

All loads remain local-only.

## First verify direct processor construction

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.smolvlm_stage4o3_direct_processor

Expected:

    Stage 4O.3 direct processor construction passed.

## Then retry real inference

    python -m forest_manager.app.local_vision_stage4k "C:\Users\yildi\Desktop\ref\ref01.png"
