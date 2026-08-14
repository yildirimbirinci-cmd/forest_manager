# Stage 4G.1 - Max 2020 Function Ordering Fix

Root cause:
`appendT2AssetGeometryJson` called `findGeometrySourceIndexByName` before that helper
was defined in the MAXScript file. On 3ds Max 2020 this resolved to `undefined` at
runtime and produced:

    Type error: Call needs function or class, got: undefined

Fix:
Move `findGeometrySourceIndexByName` above `appendT2AssetGeometryJson`.

No Stage 4G behavior or probability logic was otherwise changed.

Bridge version: 0.7.2
