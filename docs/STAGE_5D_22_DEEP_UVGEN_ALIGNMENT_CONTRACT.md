# Stage 5D.22 - Deep UVGen Alignment Contract Probe

Stage 5D.21 confirmed the Forest-level alignment values, but the bound
Bitmaptexture exposes a nested `coords` object of class StandardUVGen.

This stage reads the StandardUVGen property contract directly so Forest
Manager can distinguish:

- Forest Image Mode world-space map size and offset
- Bitmaptexture UV offset / tiling / map channel behavior

No values are changed.

The probe also reports the verified spline width, height and center in meters
using the active 3ds Max scene unit conversion.

Safety:
- read-only
- all prepared species Forest layers remain disabled
- FM_Forest_001 remains untouched
- 75.0 m Density Units remain untouched
- no bitmap coordinate is changed
- no user spline or source geometry is modified

Bridge version: 0.9.36
