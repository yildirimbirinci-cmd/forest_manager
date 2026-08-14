# Stage 4E.1 - Calibrated 45K Density

The test spline is currently approximately 450000 mm in diameter.

Instead of assuming the spline's bounding-box area equals its real closed area,
this version performs closed-loop calibration:

1. Estimate initial Units from the spline bounding box and a 45000 item target.
2. Rebuild Forest and read the real generated item count.
3. Correct Units using `sqrt(actual_count / target_count)`.
4. Rebuild again.
5. If the result is still more than 5 percent from target, perform one final correction.

This works for circular and irregular closed splines without hard-coding a 450000 mm
diameter or a circle-area formula.

Run after reloading the bridge:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.t2_target_density_stage4e_smoke

Inspect:
- pass1_items
- pass2_items
- generated_items_after
- units_x / units_y

The intended target is approximately 45000 generated Forest items.
