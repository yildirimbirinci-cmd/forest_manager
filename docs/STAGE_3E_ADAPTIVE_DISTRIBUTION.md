# Stage 3E - Adaptive Distribution

Target: 3ds Max 2020 + Forest Pack Pro 9.4.0.

Runtime inspection showed that the verified Forest object had:

- `units_x = 10000.0`
- `units_y = 10000.0`
- `distmode = 0`
- `mapname = dense.bmp`
- `manualupdate = false`

The Geometry List and Custom Object link were already verified.

Stage 3E therefore changes only the distribution cell size. It finds the Forest's spline
Area, reads its world-space bounding box, and chooses an adaptive unit size equal to about
one twentieth of the narrower area dimension, clamped to 1..500 scene units.

The previous unit values are preserved and restored if assignment/verification fails.

## Run

1. Keep the current verified scene open:
   - one Forest object
   - `Line001` Area
   - one Custom Object geometry item
2. Stop the old bridge:
       ForestManagerBridge.stop()
3. Reload/evaluate `maxscripts/ForestManager_Bridge.ms`.
4. Run:
       $env:PYTHONPATH = "$PWD\src"
       python -m forest_manager.app.forest_distribution_stage3e_smoke

Expected terminal result:

    Stage 3E adaptive distribution acceptance passed.

Then visually verify scatter inside the spline.

No scene save/export is performed.
