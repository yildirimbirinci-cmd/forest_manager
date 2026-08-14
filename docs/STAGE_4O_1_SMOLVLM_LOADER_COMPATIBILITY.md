# Stage 4O.1 - SmolVLM Loader Compatibility Fix

The previous loader hid the underlying Transformers exception.

This update:

- removes AutoModelForMultimodalLM from the active load path,
- tries the official SmolVLM AutoModelForVision2Seq path first,
- falls back to Idefics3ForConditionalGeneration because the bundled
  SmolVLM-500M config declares that architecture,
- preserves strict offline loading,
- includes the real exception class and message if loading still fails,
- adds a local diagnostic command.

Run:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.smolvlm_stage4o1_diagnostics

Then retry:

    python -m forest_manager.app.local_vision_stage4k "C:\Users\yildi\Desktop\ref\ref01.png"

If loading still fails, send the complete new error. It will now contain the
actual Transformers/PyTorch root cause.
