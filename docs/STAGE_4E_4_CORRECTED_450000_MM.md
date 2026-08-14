# Stage 4E.4 - Corrected 450000 mm UI Baseline

The current 3ds Max scene unit scale displays Forest Pack Distribution values at
10x the raw scene-unit property value.

Therefore the correct bridge value is:

    units_x = 45000.0 scene units
    units_y = 45000.0 scene units

which is displayed by Forest Pack as:

    X Units = 450000.0 mm
    Y Units = 450000.0 mm

Max Density remains:

    10 Mill.

Run:

    ForestManagerBridge.stop()

Reload/evaluate the updated bridge, then:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.t2_fixed_distribution_stage4e2_smoke

Confirm Forest Pack UI displays exactly 450000.0 mm for X and Y.
