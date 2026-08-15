Forest Manager Stage 5D.25 merge-step diagnostic update

Run from the Forest Manager project root:
python .\apply_stage5d25_merge_diagnostics.py

Then run:
python -m pytest -q tests/test_stage5d25_merge_step_diagnostics.py tests/test_stage5d25_verified_species_baseline_recovery.py

Then, with 3ds Max open and the intended closed spline selected:
python -m forest_manager.app.restore_species_baseline_stage5d25

The new error label identifies the exact failing MaxScript step without changing the verified merge algorithm.
