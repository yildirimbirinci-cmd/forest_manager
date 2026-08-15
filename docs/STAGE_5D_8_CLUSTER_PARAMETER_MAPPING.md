# Stage 5D.8 - Cluster Parameter Mapping

Purpose:
map the exact Forest Pack 9.4 MaxScript properties behind the Clusters UI
without changing the scene.

The probe searches the live Forest object for property names related to:
- diversity
- cluster / clump
- size
- roughness
- blurry edge
- noise
- geometry selection / spread / randomization

It also reports the current diversity mode, distribution mode, map name, and
density units for context.

This stage is read-only. It does not modify:
- density
- probabilities
- scale variation
- rotation
- translation
- diversity mode
- spline or unrelated scene objects

Bridge version: 0.9.23
