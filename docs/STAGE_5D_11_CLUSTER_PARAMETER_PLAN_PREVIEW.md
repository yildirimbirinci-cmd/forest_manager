# Stage 5D.11 - Cluster Parameter Plan Preview

This stage is read-only.

Verified Forest Pack mapping:
- divers = Diversity mode
- clusize = Cluster Size
- clurough = Roughness
- cluedge = Blurry Edge
- clunoise = Noise

Initial Forest Manager natural-cluster policy:
- preserve current Cluster Size
- Roughness = 35%
- Blurry Edge = 25%
- Noise = 10%

These percentages are Forest Manager's initial conservative visual policy,
not iToo defaults. They are intended for the first controlled viewport
comparison and may later be derived automatically from reference-image
composition analysis.

Cluster Size remains unit-aware. The live system-unit value is converted using
the active 3ds Max scene's `one_meter_system_units`; no global meters/cm
assumption is made.

Protected:
- Diversity remains Clusters
- current cluster size
- 75.0 m density
- geometry probabilities
- native scale variation
- rotation disabled
- translation disabled
