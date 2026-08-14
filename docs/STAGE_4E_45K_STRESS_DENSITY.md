# Stage 4E - 45K Forest Stress Density

This is a deliberate stress/calibration test after the spline Area was enlarged.

The command reads the current Forest Area spline bounding box and derives a first-pass
square Distribution unit size intended to produce approximately 45,000 Image
Distribution candidates:

    units = sqrt(bounding_box_area / 45000)

The real Forest-generated item count is returned after rebuilding. Because the spline
shape and Forest distribution bitmap affect the final count, 45,000 is a target rather
than an exact guarantee.

Initial acceptance window:

    35,000 <= generated_items_after <= 55,000

Run:

    ForestManagerBridge.stop()

Reload/evaluate the updated bridge, then:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.t2_target_density_stage4e_smoke

This test is intentionally dense and should be used to observe Forest Pack viewport
responsiveness with the real T2 CProxy source.
