# Stage 5D.5 - Layered Plant Composition Preview

This stage is read-only. It does not modify the 3ds Max scene.

Verified baseline carried forward:

- Forest: `FM_Forest_001`
- Density: exactly `75.0 m`
- Probabilities: `42.8571 / 28.5714 / 28.5715`
- Native scale variation: enabled with existing Forest Pack limits
- Rotation: disabled
- Translation: disabled

Deterministic semantic layer roles:

- Lavandula / Lavender -> `foreground_mass`
- Flowering / Butomus -> `mid_accent`
- Bush / Berberis / Shrub -> `structural_shrub`

The preview preserves current Forest probabilities and transform state. It only
adds semantic composition roles for the next apply stage. No grouping or
layer-distribution behavior is applied until the preview is accepted.
