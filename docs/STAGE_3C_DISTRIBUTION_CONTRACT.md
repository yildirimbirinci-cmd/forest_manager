# Stage 3C - Distribution contract probe

Read-only diagnostic for 3ds Max 2020 + Forest Pack Pro 9.4.0.

The Geometry List connection is already verified. This probe inspects the actual
installed Forest Pack object's distribution-related properties before Forest Manager
writes any distribution settings.

## Run

1. Keep the current scene open with:
   - `FM_Forest_001`
   - `Line001` as Area
   - one verified Custom Object geometry entry
2. Stop the previous bridge:
       ForestManagerBridge.stop()
3. Reload/evaluate `maxscripts/ForestManager_Bridge.ms`.
4. Run:
       $env:PYTHONPATH = "$PWD\src"
       python -m forest_manager.app.forest_distribution_contract_probe
5. Send the complete `Forest Distribution Contract` JSON output.

The probe does not mutate, save, or export the scene.
