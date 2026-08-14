# Stage 5C.7 - Unit-Aware Scene Measurements

This stage extends active-scene unit detection into measurement reporting without changing Forest Pack placement behavior.

Added:
- GET_SELECTION_MEASUREMENTS bridge command.
- Raw system-unit and active Display Unit values for selected node bounding dimensions.
- Active Display Unit fields for T2 source dimensions.
- System-unit and active Display Unit reporting for the -1500 mm reference-source Z offset.
- Active Display Unit fields for Forest units_x / units_y outputs.
- Automatic bridge preflight upgraded to bridge 0.9.15.

No density value, geometry probability, Forest distribution mode, or placement behavior is changed.
