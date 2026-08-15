# Stage 5D.12 - Apply Natural Cluster Profile

Applies the first controlled Forest Manager cluster-shape profile.

Changed:
- clurough = 35.0
- cluedge = 25.0
- clunoise = 10.0

Protected:
- divers remains 2 (Clusters)
- clusize remains unchanged
- density remains unchanged
- geometry probabilities remain unchanged
- scale variation remains unchanged
- rotation remains unchanged
- translation remains unchanged

The bridge reads all protected values before modification, applies only the
three target cluster-shape properties, reads state back, and restores the
previous state if verification fails.

Cluster size reporting is unit-aware and uses the active 3ds Max scene's
`units.decodeValue "1m"` conversion.

Bridge version: 0.9.25
