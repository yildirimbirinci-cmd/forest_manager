# Stage 2 - Forest Pack Integration

Target environment:

- 3ds Max 2020
- Forest Pack Pro 9.4.0
- Forest Manager bridge: 0.2.0
- Localhost port: 49491

## Scope

Stage 2 adds only:

1. Forest Pack Pro availability detection.
2. Closed-spline validation.
3. Creation of one new Forest object.
4. Addition of the selected spline as an Include Area.
5. Post-creation verification that the Forest Area points to the selected spline.
6. Automatic deletion of the newly created Forest object if Stage 2 creation/verification throws an error.

No T2 assets, geometry list entries, distribution tuning, image analysis, saving, or exporting are performed.

## Important

Reload `maxscripts/ForestManager_Bridge.ms` in 3ds Max before running the Stage 2 smoke test. This replaces the Stage 1 bridge instance with bridge version 0.2.0.

## Acceptance test

1. Open 3ds Max 2020.
2. Run `maxscripts/ForestManager_Bridge.ms`.
3. Create or use one closed Line.
4. Select only that Line.
5. From the Forest Manager repository root:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.forestpack_stage2_smoke

Expected:

- Bridge reports Max 2020.
- Forest Pack reports `available: true`.
- Selection reports a closed spline.
- A new object named `FM_Forest_001` (or the next free numeric name) is created.
- `area_count` is at least 1.
- `area_node` equals the selected Line name.
- `include` is true.
- `verified` is true.
- Final line: `Stage 2 acceptance passed.`

## Scene check

Select the newly created Forest object and inspect its Areas rollout. The selected Line should be present as an Include spline area.

The Forest contains no Geometry List model yet, so no vegetation scatter is expected in Stage 2.

## Failure safety

If Forest construction or Area verification raises an error, the bridge attempts to delete only the Forest node created by that command. It never deletes or modifies the source spline.

## Stop bridge

In MAXScript Listener:

    ForestManagerBridge.stop()
