# Stage 4E.3 - Safe Distribution Baseline

Real-scene acceptance on 3ds Max 2020 + Forest Pack Pro 9.4.0 established this
stable baseline for the enlarged Line:

- X Units: 450000.0 mm
- Y Units: 450000.0 mm
- Max Density: 10 million

The earlier 45K target calibration is no longer part of the active workflow.

This command applies and verifies the safe baseline before Forest Manager proceeds
to multi-asset T2 Geometry List integration.

Run:

    ForestManagerBridge.stop()

Reload/evaluate the updated bridge, then:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.t2_fixed_distribution_stage4e2_smoke

Expected:

    Stage 4E.3 safe-density baseline acceptance passed.

Confirm Forest Pack UI shows:

- Units X = 450000.0 mm
- Units Y = 450000.0 mm
- Max density = 10 Mill.
