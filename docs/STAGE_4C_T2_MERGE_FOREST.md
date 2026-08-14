# Stage 4C - T2 Asset Merge to Forest Pack

This is the first end-to-end T2 integration acceptance step.

Flow:

1. Forest Manager searches the real T2 library catalog.
2. It resolves an existing `.max` asset path.
3. The path is sent to the Forest Manager 3ds Max bridge as UTF-8 Base64.
4. 3ds Max merges the asset with the same core options used by T2:
   `#select #autoRenameDups #useMergedMtlDups quiet:true`.
5. Forest Manager detects only the newly merged scene nodes.
6. A top-level group head is preferred as the Forest source; otherwise a
   top-level geometry/root node is used.
7. The existing Forest Geometry item is normalized to Custom Object mode and
   rebound to the merged T2 source.
8. The verified adaptive Distribution settings and build state are preserved.
9. The bridge reports the merged nodes, selected Forest source, and generated
   Forest item count.

The default acceptance asset is:

    Acer campestre (Field maple)

## Run

Keep the current verified `FM_Forest_001` scene and spline open.

Stop and reload the bridge:

    ForestManagerBridge.stop()

Evaluate the updated `maxscripts/ForestManager_Bridge.ms`.

Then run from the Forest Manager repository root:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.t2_merge_forest_stage4c_smoke

A different T2 asset can be tested by passing search text:

    python -m forest_manager.app.t2_merge_forest_stage4c_smoke "Alnus glutinosa"

No scene save is performed automatically.
