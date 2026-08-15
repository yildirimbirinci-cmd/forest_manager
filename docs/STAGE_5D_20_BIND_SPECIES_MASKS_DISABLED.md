# Stage 5D.20 - Bind Species Distribution Masks While Disabled

Stage 5D.19 confirmed the live Forest Pack 9.4 contract:
- `distmode = 0` is Image Mode
- `distmap` accepts a custom map
- `densityMap` controls grayscale density interpretation

This stage assigns the three Stage 5D.18 soft PNG masks as Bitmaptexture maps
to the three prepared species Forest layers.

Safety:
- all species layers must already be disabled
- layers stay disabled after binding
- FM_Forest_001 remains active and is not modified
- Density Units X/Y are captured and restored to exactly the same values
- map filename, densityMap state, Image Mode and density values are verified
- any failure rolls every changed layer back to its previous map state
- no source geometry, spline or asset is modified

This stage validates binding only. It does not claim spatial alignment is
correct yet. Spatial map scale/offset/alignment is validated before activation
in the next stage.

Bridge version: 0.9.34
