# Stage 4O.6 - Robust Local Semantic Output

The model now reaches generation successfully.

Observed failure:

    SmolVLM output did not contain a JSON object.

A 500M vision-language model should not be treated as a strict JSON generator.
Forest Manager now uses an easier machine-readable line protocol:

    STYLE: ...
    DENSITY: low|medium|high
    DIVERSITY: low|medium|high
    CANOPY_BIAS: ...
    NOTES: ...; ...
    PLANTS: query|weight; query|weight
    CONFIDENCE: 0.0-1.0

The parser accepts both:
- valid JSON
- the line protocol above

If neither can be parsed, the runtime error now includes the raw model output
for direct diagnosis.

## Parser check

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.smolvlm_stage4o6_parser

Expected:

    Stage 4O.6 semantic parser passed.

## Real inference

    python -m forest_manager.app.local_vision_stage4k "C:\Users\yildi\Desktop\ref\ref01.png"
