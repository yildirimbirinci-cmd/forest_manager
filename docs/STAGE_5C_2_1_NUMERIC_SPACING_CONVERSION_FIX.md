# Stage 5C.2.1 - Numeric Physical Spacing Conversion Fix

Observed real runtime output:

    one_meter_system_units = 100.0
    spacing_m = 0.75
    spacing_system_units = 0.0
    units_x = 0.0
    units_y = 0.0
    generated_items_after = 0
    verified = true

This proves the original string-based conversion was unsafe.

Root cause:
Stage 5C.2 converted the float spacing to a localized string and then called
`units.decodeValue` on that string. Decimal formatting can be locale-dependent.

Fix:
use the already verified 1 meter conversion numerically:

    spacing_system_units = one_meter_system_units * spacing_m

For the current unit setup:

    Display Units = meters
    System Units = centimeters

the expected 0.75 m value is:

    1 m = 100 system units
    0.75 m = 75 system units

Additional safety:
- non-positive computed spacing now throws,
- non-positive Forest units cannot report verified=true,
- the Python CLI independently rejects non-positive returned units.

Bridge version: 0.9.6
