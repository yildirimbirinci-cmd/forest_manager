# Stage 3B - Geometry List detail probe

This probe is read-only.

It reports the runtime class, count, and first-item type/value for the Forest Pack 9.4.0 properties that Stage 3 will need to mutate safely.

Run:

    ForestManagerBridge.stop()

Reload and evaluate `maxscripts/ForestManager_Bridge.ms`, then:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.forest_geometry_detail_probe

Send the complete `Forest Geometry Contract Details` output back before the Stage 3 write patch is built.
