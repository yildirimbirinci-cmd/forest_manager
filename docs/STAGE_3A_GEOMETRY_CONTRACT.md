# Stage 3A - Forest Pack Geometry Contract Probe

Target: 3ds Max 2020 + Forest Pack Pro 9.4.0.

This diagnostic stage reads the properties exposed by the actual installed Forest Pack object before Forest Manager writes Geometry List data.

Why: ITOOSOFT recommends using `showProperties` / exposed properties against the installed version because Forest Pack parameters evolve over time.

## Run

1. Ensure a Forest object exists in the scene. The verified Stage 2 `FM_Forest_001` is sufficient.
2. Stop the old bridge in MAXScript Listener:

       ForestManagerBridge.stop()

3. Reload and evaluate:

       maxscripts/ForestManager_Bridge.ms

4. From the repository root:

       $env:PYTHONPATH = "$PWD\src"
       python -m forest_manager.app.forest_geometry_contract_probe

5. Send the full `Forest Geometry Contract` JSON output back for Stage 3 implementation.

This probe is read-only. It does not add geometry, modify the Forest, save, or export the scene.
