# Stage 5D.21 - Species Mask Spatial Alignment Contract Probe

Stage 5D.20 verified that all three generated PNG masks can be bound as
Bitmaptexture distribution maps while preserving 75.0 m Density Units.

This stage is read-only and resolves how those maps are positioned in Forest
Pack/Image Mode before any species layer is enabled.

It reports:
- Forest map channel / UV / alignment / scale-related properties
- Bitmaptexture coordinate / offset / tiling / crop / angle-related properties
- the verified area spline world bounds when available

Safety:
- all species layers remain disabled
- no bitmap coordinate is changed
- no Forest distribution property is changed
- FM_Forest_001 remains untouched
- no user spline or geometry is modified

Bridge version: 0.9.35
