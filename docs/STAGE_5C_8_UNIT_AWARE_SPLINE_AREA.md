# Stage 5C.8 - Unit-Aware Spline Area

Purpose:
calculate the physical area of the currently selected closed 3ds Max spline
without assuming a fixed Display Unit or System Unit configuration.

Runtime behavior:
- reads the currently active 3ds Max Unit Setup;
- samples each closed spline using MAXScript pathInterp;
- computes the planar loop area from sampled world-space points;
- reports raw squared system units;
- reports canonical square meters;
- reports a display-area value for metric display units;
- preserves all existing Forest Pack density behavior.

New command:

    GET_SELECTION_SPLINE_AREA

New CLI:

    python -m forest_manager.app.spline_area_stage5c8

The current user scene uses Display Units = meters and System Units =
centimeters, so area_display_unit is expected to be m2 there. The code does
not hard-code that combination.

Bridge version: 0.9.17
