# Stage 4K - Live Vision Provider

Stage 4K attaches the semantic provider contract to a real OpenAI Responses API
image-analysis adapter.

The adapter:

- reads `OPENAI_API_KEY`,
- optionally reads `FOREST_MANAGER_VISION_MODEL`,
- encodes the local reference image as a base64 data URL,
- sends it as an `input_image`,
- requests a strict semantic JSON object,
- validates the semantic result,
- builds the existing `CompositionPlan`,
- optionally applies the plan to T2 + Forest Pack.

No API key is stored in the repository.

## Environment

PowerShell / VS Code terminal:

    $env:OPENAI_API_KEY = "..."
    $env:FOREST_MANAGER_VISION_MODEL = "gpt-5"
    $env:PYTHONPATH = "$PWD\src"

## Analysis only

    python -m forest_manager.app.live_vision_stage4k "C:\path\reference.jpg"

This does not change the 3ds Max scene.

## Analyze and apply

Only after analysis-only output is satisfactory:

    python -m forest_manager.app.live_vision_stage4k "C:\path\reference.jpg" --apply

This resolves the generated queries through T2 and applies the resulting
composition plan to the active Forest object.

The provider is isolated behind `SemanticVisionProvider`, so a future local
vision model can be added without changing the rest of Forest Manager.
