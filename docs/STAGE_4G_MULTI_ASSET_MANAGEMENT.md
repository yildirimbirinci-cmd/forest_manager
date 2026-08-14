# Stage 4G - General Multi-Asset Management

Stage 4F verified two real T2 CProxy vegetation assets in one Forest Geometry List.

Stage 4G adds:

- a third real T2 vegetation asset,
- duplicate-asset rejection,
- explicit probability plans,
- automatic normalization of arbitrary positive weights to 100 percent,
- preservation of the accepted Forest density baseline.

Acceptance plan:

- Acer campestre: 40
- Alnus glutinosa: 35
- Alnus x spaethii: 25

Run:

    ForestManagerBridge.stop()

Reload/evaluate the updated bridge, then:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.t2_multi_asset_stage4g_smoke

Expected:

    Stage 4G multi-asset management acceptance passed.
