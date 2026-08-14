# Stage 4J - Semantic Vision Provider Contract

Stage 4J creates the stable interface between a real vision model and the
already-verified Forest Manager composition pipeline.

Important: this stage does NOT pretend that JSON fixture data is image
understanding. The bundled JSON provider exists only to validate the provider
contract end-to-end.

A real provider must return:

- style
- density
- diversity
- canopy bias
- composition notes
- plant candidates
- weight for each candidate
- confidence
- provider identity

That result is converted into the existing `CompositionPlan` without changing
the T2 / Forest Pack / 3ds Max integration.

Safety rules:

- confidence below the threshold is rejected,
- empty plant candidate lists are rejected,
- duplicate plant candidates are rejected,
- weights must be positive,
- automatic probabilities are normalized by CompositionPlan.

## Contract acceptance

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.semantic_vision_stage4j_smoke "C:\path\reference.jpg"

Expected:

    Stage 4J semantic vision contract acceptance passed.

The next stage can add a live vision-model adapter implementing
`SemanticVisionProvider`.
