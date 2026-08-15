# Stage 5D.16 - Per-Layer Density/Distribution Contract Probe

Stage 5D.15 successfully prepared three disabled single-species Forest layers.

Before activation, total scatter must be protected. If all three independent
layers were enabled at the same verified Density Units value of 75.0 m, each
would generate its own full distribution and total scatter could increase
substantially relative to the original combined Forest.

Forest Manager must not reinterpret or silently rescale the user-verified
75.0 m Density Units value.

This stage is therefore read-only. It scans each prepared Forest layer for
live Forest Pack 9.4 properties related to:
- density
- probability
- multipliers / ratios / percentages
- item limits and counts
- distribution controls

Goal:
find a supported per-layer weighting mechanism that preserves the verified
75.0 m Density Units field while carrying the original
42.8571 / 28.5714 / 28.5715 species weighting into separate Forest layers.

All three prepared layers must remain disabled during this probe.

Bridge version: 0.9.32
