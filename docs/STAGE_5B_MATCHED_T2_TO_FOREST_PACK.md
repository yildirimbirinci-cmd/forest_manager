# Stage 5B - Matched T2 Assets to Forest Pack

Purpose: turn validated Stage 5A semantic matches into the first visible Forest
Pack result in 3ds Max.

Selection policy:
- choose the best real T2 match for each matched semantic term,
- do not substitute unmatched terms,
- use equal probability per matched semantic term for this first visual pass,
  because the current local vision output does not yet provide trustworthy
  quantitative coverage weights.

Managed scene policy:
- user selects exactly one closed spline,
- RESET_MANAGED_FOREST_FROM_SELECTION recreates only FM_Forest_001,
- if an object named FM_Forest_001 exists but is not Forest_Pro, reset aborts,
- unrelated scene objects are not deleted,
- previous FM_References may remain hidden; newly merged sources are normalized
  to FM_References at Z = -1500 mm,
- accepted distribution baseline remains units_x/y = 45000 and maxdensity = 10.

The new bridge reports version 0.9.0.

## 1. Reload the updated MaxScript bridge

Load/evaluate maxscripts/ForestManager_Bridge.ms in 3ds Max 2020 so PING reports
bridge 0.9.0.

## 2. Preview with no scene changes

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.t2_forest_apply_stage5b --text "PLANTS: lavender purple white lillies flowers shrubs plants."

Expected selected semantic groups from the current T2 library:
- lavender -> Lavandula ...
- flower -> one best flowering asset
- shrub -> one best Bush_* asset
- lily remains unmatched if no real lily/lilium asset exists

## 3. First visible 3ds Max result

In 3ds Max, select exactly one closed Line/Spline. Then run:

    python -m forest_manager.app.t2_forest_apply_stage5b --apply --text "PLANTS: lavender purple white lillies flowers shrubs plants."

Expected:
- FM_Forest_001 is recreated on the selected spline,
- three real matched T2 assets are merged and bound,
- probabilities total 100,
- FM_References is hidden and sources are at Z = -1500 mm,
- Forest Pack uses the accepted fixed distribution baseline,
- viewport shows the first reference-derived automatic planting result.
