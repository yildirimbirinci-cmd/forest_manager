# Stage 5B.2 - Max 2020 Reference Helper Order Fix

Observed runtime failure:

    Could not append T2 asset ...
    Type error: Call needs function or class, got: undefined

Root cause:

`appendT2AssetGeometryJson()` called `prepareReferenceNode()` before that
function was defined inside the ForestManagerBridge struct. In 3ds Max 2020,
this forward reference can resolve as `undefined`.

Fix:

- move `getOrCreateReferenceLayer()` before `prepareReferenceNode()`
- move both functions before `appendT2AssetGeometryJson()`
- preserve reference-source behavior:
  - layer = FM_References
  - Z = -1500mm
  - layer visibility off
- bridge version = 0.9.2
- retain the Stage 5B.1 bare `throw` fix

No T2 matching, probability, density, or Forest Pack distribution behavior was
changed.
