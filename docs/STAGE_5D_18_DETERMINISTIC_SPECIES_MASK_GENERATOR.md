# Stage 5D.18 - Deterministic Species Mask Generator

This stage creates real grayscale PNG masks, but does not bind them to Forest
Pack and does not activate any prepared species Forest layer.

## Output

Default output directory:

`resources/generated_masks/stage5d18`

For each species role, two files are written:

- `_primary.png`: binary exclusive ownership mask
- `.png`: Gaussian-softened grayscale distribution mask

## Coverage targets

- foreground_mass: 42.8571%
- mid_accent: 28.5714%
- structural_shrub: 28.5715%

Primary ownership is exact by pixel quota: every pixel belongs to exactly one
species. This prevents hidden triple-coverage in the primary partition.

Soft masks are derived only after the exclusive partition is verified. They
are intended for Forest Pack edge blending in a later stage.

## Determinism

The generator uses a fixed seed and deterministic analytic fields. Re-running
with the same dimensions and seed produces byte-identical PNG masks.

## Safety

Stage 5D.18 does not:
- connect to 3ds Max
- modify Forest Pack
- enable species layers
- disable the legacy Forest
- modify Density Units
- modify the user spline
- merge any asset

Stage 5D.19 will probe and validate the exact Forest Pack bitmap/map binding
contract before any mask is applied.
