# Stage 5D.3 - Transform Plan Preview

Purpose:
create a safe, read-only transform plan from the live Forest Pack 9.4
properties discovered in Stage 5D.2.

Rules:
- no Forest property is changed;
- Density Units stay exactly 75.0 m;
- existing composition probabilities are preserved;
- no translation or rotation is enabled;
- scale limits are not invented: the preview copies the native values read
  from the live Forest object;
- the proposed next step is only to enable scale while preserving those live
  native limits.

The user's current live Forest reported:
- applyscale = false
- scalexmin/scalexmax = 80/120
- scaleymin/scaleymax = 80/120
- scalezmin/scalezmax = 100/100
- scalelock = 1
- ScaleList = 100/100/100

This stage does not assume those numbers for every scene. They are read again
from the active Forest object at runtime.
