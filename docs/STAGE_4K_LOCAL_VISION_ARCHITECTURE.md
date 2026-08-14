# Stage 4K - Local Vision Architecture

Forest Manager reference-image analysis is now local-only.

Product rules:

- No OpenAI API.
- No API key.
- No runtime internet requirement.
- No reference image leaves the workstation.
- Approved model files live under `models/vision`.
- Model loading uses `local_files_only=True`.
- Missing model/dependencies produce an explicit error; there is no cloud fallback.
- The existing SemanticVisionProvider and CompositionPlan contracts remain intact.

The initial backend is `TransformersLocalVisionBackend`. The approved model will be
bundled in a later installer/dependency stage.

## Remove obsolete cloud-provider files

If the previous experimental Stage 4K package was extracted, run once:

    python tools/remove_obsolete_cloud_vision.py

## Local analysis

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.local_vision_stage4k "C:\path\reference.png"

Until a model has been installed under `models/vision`, the expected safe result is:

    Stage 4K Local Vision error: Local vision backend is not available...

That error is correct. Forest Manager must never silently fall back to an online API.

The next step is selecting and bundling the approved local vision-language model,
then testing it against the real `ref01.png`.
