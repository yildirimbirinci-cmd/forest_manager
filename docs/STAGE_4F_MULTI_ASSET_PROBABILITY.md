# Stage 4F - Multi-Asset T2 Geometry + Probability

Prerequisite: existing Acer T2 CProxy is already bound to Forest. The accepted density baseline remains 450000.0 mm X/Y in the UI and Max Density 10 Mill.

This stage finds `Alnus glutinosa (Black alder)` in T2, merges it, appends it as a second Forest Pack Custom Object, and equalizes Geometry probability to 50/50.

Run after reloading the bridge:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.t2_multi_asset_stage4f_smoke

Expected: `Stage 4F multi-asset probability acceptance passed.`
