# Stage 4D - Asset-Aware Forest Density

Stage 4C verified the real T2 -> 3ds Max -> CProxy -> Forest Pack chain.

The first real T2 tree reported approximately:

- source width: 542.135
- source depth: 564.932
- source height: 780.063
- generated Forest items: 40893

The previous distribution unit size was approximately 21.67, which is much smaller
than the real tree footprint and causes extreme overlap.

Stage 4D derives the Forest Distribution X/Y Units from the active T2 source object's
real horizontal bounding-box footprint:

    units_x = source_width * 1.05
    units_y = source_depth * 1.05

The 5 percent margin reduces heavy crown/proxy overlap. If the asset is larger than
the spline bounding box, spacing is capped to the corresponding area dimension.

The command modifies only Forest distribution/build properties. It does not delete
the T2 proxy, Box test object, spline, or Forest object, and it does not save the scene.

## Run

Stop/reload the updated bridge:

    ForestManagerBridge.stop()

Then:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.t2_asset_density_stage4d_smoke

Expected:

    Stage 4D asset-aware density acceptance passed.

Verify the viewport visually. The T2 vegetation scatter should be dramatically less
dense than the previous 40893-item result.
