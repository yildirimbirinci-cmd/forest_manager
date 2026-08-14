# Stage 3H - Geometry Item Normalization

The Forest Pack 9.4.0 runtime contract showed that the Custom Object link exists,
but some geometry metadata still contained template defaults:

- `cobjlist[1] = Box001`
- `geomlist[1] = 2` (Custom Object)
- `namelist[1] = Box001`
- `tempnamelist[1] = One Plane`
- `widthlist[1] = 0.0`
- `heightlist[1] = 0.0`

Stage 3H normalizes the source-specific metadata and reassigns the Custom Object
after Custom Object mode is set. It also attempts to report the generated item count
through Forest Pack's `trees` interface when available.

Run:

    ForestManagerBridge.stop()

Reload/evaluate `maxscripts/ForestManager_Bridge.ms`, then:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.forest_geometry_stage3h_smoke

No scene save/export is performed.
