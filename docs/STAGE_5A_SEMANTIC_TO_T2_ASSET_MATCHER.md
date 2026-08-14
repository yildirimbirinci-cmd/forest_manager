# Stage 5A - Semantic to T2 Asset Matcher

Goal:
convert imperfect local-vision vegetation observations into candidate assets
that actually exist in the T2 library.

Important rule:
the matcher never creates or invents an asset name. Every result must be
returned by the real T2AssetCatalog and must point to a `.max` file.

The matcher accepts partial model output such as:

    PLANTS: lavender purple white lillies flowers shrubs plants.

It removes visual-only/generic words, normalizes common plurals, and expands
limited botanical search synonyms such as:

    maple -> acer
    alder -> alnus
    lavender -> lavandula
    lily -> lilium

Stage 5A is preview-only. It does not alter 3ds Max.

## Test with the last real SmolVLM observation

From the project root:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.t2_asset_matcher_stage5a --text "PLANTS: lavender purple white lillies flowers shrubs plants."

The output shows:
- semantic terms extracted from the vision result,
- real T2 `.max` matches,
- unmatched observations.

If the current T2 library has no lavender/lily/shrub assets, an empty result is
correct and safer than substituting an unrelated tree.

Stage 5B will connect validated real T2 matches to the existing composition and
Forest Pack application pipeline.
