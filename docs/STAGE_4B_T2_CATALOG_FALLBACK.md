# Stage 4B - T2 Catalog Fallback

Forest Manager first reads T2's SQLite asset index. If no existing `.max` asset is available there, it reads T2's own `%LOCALAPPDATA%\\T2Manager\\Config\\settings.json` and scans configured library roots read-only.

Roots used: `library_path`, `local_sync_path`, `project_library_path`, and paths in `external_libraries`.

Run:

    $env:PYTHONPATH = "$PWD\\src"
    python -m forest_manager.app.t2_catalog_stage4b_smoke

The JSON also reports database row counts and resolved T2 library roots.
