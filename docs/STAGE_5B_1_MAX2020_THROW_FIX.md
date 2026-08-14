# Stage 5B.1 - 3ds Max 2020 Catch/Throw Fix

Observed MaxScript compile error:

    only throws without arguments are permitted in catch expressions
    In line: throw message

Root cause:

`resetManagedForestFromSelectionJson` attempted to rethrow the captured
exception with:

    throw message

3ds Max 2020 requires a bare rethrow inside `catch`:

    throw

The exception text is still written to the MaxScript Listener before the
rethrow.

Bridge version: 0.9.1

No Forest Pack behavior, T2 matching, geometry probability, density baseline,
or reference-layer behavior was changed.
