# Stage 5C.3 - Native Density Calibration

Observed runtime/viewport baseline:

- Display Unit Setup: meters
- System Unit Setup: centimeters
- Forest Pack Density > Units shown in UI: 75.0 m
- Area spline: approximately 100 square meters
- Viewport: populated successfully

Decision:

Forest Manager no longer interprets Forest Pack `units_x` / `units_y` as a generic
physical-meter conversion target. The bridge sets the Forest native Density Units
value directly. The first observed calibration baseline is 75.0.

The existing `trees.count()` probe is retained for diagnostics only. A zero value is
not treated as authoritative proof that the viewport has no generated Forest items,
because the real 3ds Max viewport demonstrated populated output while the probe
returned zero.

Acceptance:

    python -m forest_manager.app.density_stage5c3 --density 75

Expected:

- units_x = 75
- units_y = 75
- verified = true
- viewport remains populated

Bridge version: 0.9.7
