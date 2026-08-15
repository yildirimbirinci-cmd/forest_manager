# Stage 5D.6 - Distribution Capability Probe

Purpose: inspect the live Forest Pack 9.4 object before implementing layered/grouped planting behavior.

This stage is read-only. It enumerates properties whose names relate to distribution, maps, clustering, grouping, falloff, or edges. It also reports the current density units but does not change them.

Protected state remains unchanged:
- Density Units = current live value (75.0 m in the verified scene)
- geometry probabilities
- native scale variation
- rotation and translation states
- user spline and unrelated scene objects

Bridge version: 0.9.21
