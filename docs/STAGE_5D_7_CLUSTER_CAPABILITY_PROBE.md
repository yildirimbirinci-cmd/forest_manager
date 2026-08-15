# Stage 5D.7 - Cluster Capability Probe

Purpose:
identify the exact Forest Pack 9.4 MaxScript properties related to
Distribution > Diversity > Clusters before modifying the live scene.

Why:
Stage 5D.6 confirmed that `keepgrouplist` belongs to Geometry group hierarchy,
not to plant-cluster composition. Forest Pack documentation identifies
Distribution > Diversity > Clusters as the intended natural grouping feature.

This stage is strictly read-only. It scans the live Forest object for property
names related to:
- cluster / clump
- diversity
- geometry selection
- probability
- colour/color IDs

Protected state:
- density
- probabilities
- scale variation
- rotation
- translation
- spline and unrelated scene objects

Bridge version: 0.9.22
