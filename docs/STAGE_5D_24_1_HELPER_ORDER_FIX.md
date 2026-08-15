# Stage 5D.24.1 - MAXScript Helper Order Fix

Root cause:
`applySpeciesUvClampPreviewJson()` and
`rollbackSpeciesUvClampPreviewJson()` were defined before
`getSpeciesPreviewNodes()` inside the Forest Manager MAXScript struct.

3ds Max 2020 MAXScript does not safely resolve this forward reference in the
current struct layout, so the runtime call resolved to `undefined` and failed
with:

`Type error: Call needs function or class, got: undefined`

Fix:
- define `getSpeciesPreviewNodes()` first
- define UV clamp apply/rollback functions after it
- do not change UV clamp behavior
- do not change Density Units, maps, offsets, clusters, sources, or spline

Bridge version: 0.9.39
