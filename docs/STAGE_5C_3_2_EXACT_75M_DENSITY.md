# Stage 5C.3.2 - Exact 75 Meter Density

Accepted Max-side requirement:

- Display Unit Setup: meters
- System Unit Setup: centimeters
- Forest Pack Density Units X: 75.0 m
- Forest Pack Density Units Y: 75.0 m

No alternative density value is substituted.

The command accepts meters as the user-facing value. With centimeters as the
3ds Max System Unit, 1 meter is 100 system units, so 75.0 m is written
internally as 7500 system units. This internal conversion exists only to make
Forest Pack display and use the requested 75.0 m value.

Default command:

    python -m forest_manager.app.density_stage5c3

Explicit command:

    python -m forest_manager.app.density_stage5c3 --density-m 75

Bridge version: 0.9.9
