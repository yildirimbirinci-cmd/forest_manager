# Stage 3F - Forest Build-State Normalization

This stage normalizes the Forest object's build state after Area, Geometry, and
Distribution have already been verified.

It explicitly enables Forest building (`disabled = false`), keeps automatic updates
enabled (`manualupdate = false`), re-applies adaptive distribution units, notifies
dependents, and redraws the viewport.

No scene save/export is performed.

Run:

    ForestManagerBridge.stop()

Reload/evaluate `maxscripts/ForestManager_Bridge.ms`, then:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.forest_build_state_stage3f_smoke

The terminal must end with:

    Stage 3F build-state acceptance passed.

Then check whether scatter appears inside the spline.
