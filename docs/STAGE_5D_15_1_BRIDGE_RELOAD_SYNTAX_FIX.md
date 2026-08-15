# Stage 5D.15.1 - Bridge Reload Syntax Fix

Root cause:
Stage 5D.15 introduced `throw message` inside the transactional catch block.
For the 3ds Max 2020 MAXScript runtime used by Forest Manager, rethrowing from
that catch must use bare `throw`.

Because the new script failed during `fileIn`, the running 0.9.29 bridge stayed
alive and automatic preflight correctly reported a version mismatch.

Fix:
- preserve transactional cleanup
- replace `throw message` with bare `throw`
- bump bridge/runtime expectation to 0.9.31

No species-layer behavior was otherwise changed.
