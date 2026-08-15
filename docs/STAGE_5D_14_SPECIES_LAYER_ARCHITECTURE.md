# Stage 5D.14 - Species Layer Architecture Preview

## Decision

The verified single-Forest cluster calibration is retained as the current
baseline, but it cannot provide truly independent spatial behavior for each
species because Forest Pack's Diversity/Clusters controls apply at the Forest
object level.

Forest Manager therefore moves to a multi-Forest species-layer architecture:

- one managed Forest layer per species
- the same verified spline area references
- the same existing managed source nodes
- independent distribution controls per layer

The existing `FM_Forest_001` remains unchanged during migration and is used as
the rollback source until the split layers are verified in the viewport.

## Why this architecture is supported

Official Forest Pack documentation describes multiple Forest objects sharing
common area/source organization through Forest Sets, and the Areas rollout
supports spline areas for Forest scatters. Forest Pack 8 documentation also
describes assigning a spline in a master Forest and reusing it from other
Forest objects.

## Safety

Stage 5D.14 is read-only.

The next runtime stage must:
- create only Forest Manager-owned layers
- reuse sources instead of merging duplicate assets
- reuse the verified spline areas
- preserve active-scene unit handling
- verify all new layers before disabling the combined Forest
- preserve the combined Forest for rollback until viewport acceptance
- never delete the user spline or unrelated scene objects

Bridge version: 0.9.27
