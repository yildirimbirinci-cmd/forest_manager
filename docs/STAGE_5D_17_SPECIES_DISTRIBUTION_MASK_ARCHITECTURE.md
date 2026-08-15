# Stage 5D.17 - Species Distribution Mask Architecture Preview

## Purpose

Separate species spatial composition without changing the user-verified
Forest Pack Density Units value of 75.0 m.

## Decision

The original semantic weights:

- Lavandula: 42.8571%
- Butomus: 28.5714%
- Berberis: 28.5715%

will no longer be interpreted as independent per-Forest density values.
Instead, they become target spatial coverage shares for three complementary
distribution masks.

## Spatial roles

- foreground_mass: largest connected planting masses
- mid_accent: smaller separated accent islands
- structural_shrub: medium-to-large structural islands

The masks share the same area coordinate space and should use soft boundaries
while keeping primary regions mutually exclusive enough to avoid tripling the
scatter.

## Safety

This stage is read-only.

- The three prepared Forest layers remain disabled.
- FM_Forest_001 remains active.
- Density Units remains 75.0 m.
- Existing CProxy source nodes are preserved.
- The user spline is not modified.
- No bitmap or Forest map is written in this stage.

Next:
Stage 5D.18 will generate deterministic complementary masks and validate their
coverage numerically before any Forest layer is activated.
