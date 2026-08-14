# Stage 5C.4 - Active Scene Unit Detection

Forest Manager no longer treats one fixed Display/System Unit configuration as a global application assumption.

The bridge now reads the unit context from the currently active 3ds Max scene at runtime using the native MAXScript `units` struct:

- `units.DisplayType`
- `units.MetricType` / `units.USType` / custom unit fields
- `units.SystemType`
- `units.SystemScale`
- `units.decodeValue()` for physical-to-system conversion
- `units.formatValue()` for system-to-current-display formatting

New bridge command:

    GET_SCENE_UNITS

The response includes the active display unit, system unit type/scale, conversion factors, and a formatted one-meter sample.

Density remains explicitly requested as 75.0 meters in the current acceptance workflow. It is converted to system units using the active scene at runtime and the response now also reports the value formatted using the active Display Unit Setup.

The physical FM_References offset remains exactly -1500 mm, but its internal value is now produced through the shared scene-unit-aware conversion helper.

This stage establishes the common unit contract. Subsequent unit-sensitive features should consume the same runtime unit context rather than introducing fixed scale assumptions.

Bridge version: 0.9.12
