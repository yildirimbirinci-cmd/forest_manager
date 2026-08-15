# Stage 5A.1 - Term-Scoped T2 Matching

Observed real Stage 5A defect:

    source_term = lily
    asset = Bush_Berberis

and

    source_term = lily
    asset = Bush_Choisya

Root cause:
the matcher expanded every semantic source term using the global synonym list.
This allowed a term such as `lily` to query `bush`, which belongs only to the
`shrub` semantic term.

Fix:
each semantic term now owns only its own search variants.

Examples:

    lavender -> lavender, lavandula
    lily     -> lily, lilium
    flower   -> flower
    shrub    -> shrub, bush
    maple    -> maple, acer
    alder    -> alder, alnus

The matcher still returns only real T2 `.max` files.

No 3ds Max changes are made in this stage.

## Re-run the last real observation

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.t2_asset_matcher_stage5a --text "PLANTS: lavender purple white lillies flowers shrubs plants."

Expected behavior:
- Lavender may match Lavandula.
- Flower may match flowering assets.
- Shrub may match Bush_* assets.
- Lily must not match Bush_* assets.
- If no lily/lilium asset exists, lily must appear under unmatched_terms.
