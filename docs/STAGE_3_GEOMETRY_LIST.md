# Stage 3 - Geometry List write acceptance

Target: 3ds Max 2020 + Forest Pack Pro 9.4.0.

## Scope

This stage performs the first real Geometry List write.

It uses the verified Stage 2 Forest object and one selected scene geometry object.
The command grows the known Forest Pack Geometry List arrays, assigns the selected
source, sets probability to 100, and verifies the node/name link after the write.

If any mutation or verification fails, the bridge attempts to restore every Geometry
List array count changed by the command.

## Preparation

1. Keep `FM_Forest_001` from Stage 2 in the scene.
2. Create a simple Box, Sphere, or other geometry object.
3. Select only that geometry object.
4. Stop the previous bridge:

       ForestManagerBridge.stop()

5. Reload/evaluate `maxscripts/ForestManager_Bridge.ms`.

The bridge version should report `0.4.0`.

## Run

From repository root:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.forest_geometry_stage3_smoke

Expected terminal result:

    Stage 3 geometry-list acceptance passed.

Then inspect `FM_Forest_001 > Geometry`. The selected source should appear there.

## Visual scatter check

Because this is the first write against the actual Forest Pack 9.4.0 runtime,
the terminal verification and the viewport result are treated separately.

- If the source is present in Geometry and scatter appears inside the spline:
  Stage 3 is fully accepted.
- If the source is present but scatter does not appear:
  do not manually repair the Forest. Keep the scene open and report this result.
- If the command fails:
  send the exact terminal error. The bridge will have attempted count rollback.

## Safety

The source object is not deleted, hidden, moved, or renamed.
The spline is not modified.
The scene is not saved automatically.
