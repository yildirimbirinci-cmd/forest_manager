# Stage 5C.2 - Unit-Aware Density Calibration

Current 3ds Max convention:

- Display Unit Setup: meters
- System Unit Setup: centimeters

The old fixed Forest Pack value `units_x/y = 45000` is no longer used by the
new calibration command.

The bridge accepts a physical spacing in meters and converts it with MaxScript's
own unit system:

    units.decodeValue "1m"
    units.decodeValue "0.75m"

This avoids hand-written meter/centimeter conversion and follows the active 3ds
Max System Unit Setup.

New command:

    SET_PHYSICAL_SPACING|0.75

Bridge version: 0.9.5

## Acceptance test

With an existing `FM_Forest_001` in the scene:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.density_stage5c2 --spacing 0.75

The response reports:

- one_meter_system_units
- spacing_system_units
- previous units_x/y
- new units_x/y
- generated_items_before
- generated_items_after

For System Units = centimeters, `one_meter_system_units` should resolve to the
scene's equivalent of one physical meter. The code does not assume the numeric
conversion; Max performs it.
