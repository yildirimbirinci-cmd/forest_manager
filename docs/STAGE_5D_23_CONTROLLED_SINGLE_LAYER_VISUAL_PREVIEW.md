# Stage 5D.23 - Controlled Single-Layer Visual Preview

Purpose:
Observe the real Forest Pack Image Mode sampling/alignment behavior before
inventing any map offset or tiling formula.

Default preview:
- disable FM_Forest_001 temporarily
- enable only FM_Layer_01_foreground_mass
- keep FM_Layer_02_mid_accent disabled
- keep FM_Layer_03_structural_shrub disabled

Protected state:
- Density Units stays exactly 75.0 m X/Y
- distmode stays Image Mode (0)
- densityMap stays enabled
- assigned Bitmaptexture is not modified
- cluster and transform state are not modified
- source geometry and user spline are not modified

Rollback:
`--rollback` restores FM_Forest_001 active and disables all three species
layers.

Activation and rollback both verify their resulting states and restore the
previous disabled-state snapshot if verification fails.

Bridge version: 0.9.37
