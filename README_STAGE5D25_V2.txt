Forest Manager Stage 5D.25 Merge Diagnostic Fix v2

Extract this ZIP directly into the Forest Manager project root.

Run:
python .\apply_stage5d25_merge_diagnostics_v2.py

Then:
python -m pytest -q tests/test_stage5d25_merge_step_diagnostics.py tests/test_stage5d25_verified_species_baseline_recovery.py

Then with 3ds Max open and the intended closed spline selected:
python -m forest_manager.app.restore_species_baseline_stage5d25
