# Stage 5D.1 - Semantic Composition Probabilities

Purpose: replace equal Forest geometry probabilities with a deterministic semantic plan derived from the local reference observation while preserving the current Forest density.

Policy `semantic_specificity_v1`:
- specific plant terms such as lavender/lavandula receive weight 3;
- broad categories such as flower/shrub receive weight 2;
- unmatched existing geometry remains present with a small fallback weight 0.5;
- all weights are normalized to 100 percent.

For the current reference observation and current three Forest geometry sources the expected preview is approximately:
- Lavandula: 42.8571%
- Butomus / Flowering: 28.5714%
- Bush_Berberis: 28.5715%

`--apply` is required to change Forest probabilities. The apply path reads composition context before and after the change and fails if Density Units X/Y changed. The user-requested 75.0 m density is therefore protected in this stage.

No bridge update is required; Stage 5D.1 uses the existing verified `GET_COMPOSITION_CONTEXT` and `SET_GEOMETRY_PROBABILITIES` commands from bridge 0.9.18.
