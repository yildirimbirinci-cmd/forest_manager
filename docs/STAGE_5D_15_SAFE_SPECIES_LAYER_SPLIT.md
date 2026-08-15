# Stage 5D.15 - Safe Species Layer Split Runtime

Live Forest Pack 9.4 contracts are now verified:
- `cobjlist` is the authoritative geometry source-node array.
- `arnodelist` is the authoritative area-node array.

This stage creates three managed species Forest layers:
- FM_Layer_01_foreground_mass
- FM_Layer_02_mid_accent
- FM_Layer_03_structural_shrub

Safety model:
- `FM_Forest_001` is preserved and remains the active rollback source.
- Existing expected layer names are deleted only when they are Forest Manager-owned.
- The same three existing CProxy source nodes are reused; no asset is merged again.
- The same verified spline area is reused.
- Common density, cluster and transform state is copied from the verified source Forest.
- Each new layer contains exactly one geometry source at probability 100%.
- The original combined-Forest probability is stored as metadata.
- New layers remain disabled after creation to prevent double scattering.
- If any layer creation or verification fails, every layer created in that run is deleted.

The next stage will assign role-specific distribution profiles and activate the
new layers only after another preview/verification step.

Bridge version: 0.9.30
