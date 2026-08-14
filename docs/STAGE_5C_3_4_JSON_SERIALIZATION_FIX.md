# Stage 5C.3.4 - Density JSON Serialization Fix

Real runtime evidence:

    density_m = 75.0
    one_meter_system_units = 100.0
    density_system_units = 7500.0
    units_x = 7500.0
    units_y = 7500.0
    generated_items_after = 1915

The density behavior is therefore working correctly.

The remaining failure was serialization only. The nested
configureDensityMetersJson() function emitted literal backslashes before its
JSON field quotes, producing a payload such as:

    {\"forest_name\":"FM_Forest_001",...}

This patch removes that extra escape layer only inside the nested density
payload. The outer bridge response was already correct and is preserved.

No density value, Forest Pack setting, scene behavior, or generated-item logic
was changed.

Requested Forest Pack Density Units remains exactly 75.0 meters.

Bridge version: 0.9.11
