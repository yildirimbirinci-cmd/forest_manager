# Stage 5C.7.1 - Selection Helper Order Fix

Observed runtime error:

    GET_SELECTION_MEASUREMENTS -> Call needs function or class, got: undefined

Root cause:
`getSelectionMeasurementsJson()` called `getSingleSelection()` before that helper
was declared inside the MaxScript struct. 3ds Max 2020 does not resolve this
forward reference in this struct context.

Fix:
- move `getSingleSelection()` above `getSelectionMeasurementsJson()`;
- keep measurement/unit logic unchanged;
- bump bridge and automatic preflight expectation together to 0.9.16.

No density, Forest Pack distribution, scene units, or geometry behavior changed.
