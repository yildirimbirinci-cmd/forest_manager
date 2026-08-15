# Stage 5D.14.1 - Live Source/Area Contract Probe

Stage 5D.14 exposed two invalid assumptions:

1. `tempnamelist` returned `One Plane` for all three geometry entries and
   therefore cannot be treated as the authoritative source-node contract.
2. `arnodes` returned no areas even though the verified live Forest scatter
   is bounded by the user's spline.

No layer split is allowed until these live Forest Pack 9.4 contracts are
resolved.

This read-only probe reports:
- Forest properties whose names suggest geometry/source/area/spline/node usage
- every property whose value is a direct scene node
- every ArrayParameter/Array property containing scene nodes
- Forest Manager-owned nodes currently present in the `FM_References` layer

The probe does not depend on the current 3ds Max selection and does not modify
the scene.

Bridge version: 0.9.28
