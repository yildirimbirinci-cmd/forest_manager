# Stage 4A - T2 Asset Catalog Integration

Forest Manager reads the existing T2 Asset Manager SQLite index directly in
read-only mode. It does not import T2 UI/Core modules and does not mutate T2 data.

T2 contract verified from the supplied source:

- Database: `%LOCALAPPDATA%\T2Manager\Database\assets.db`
- Table: `assets`
- Asset path: `file_path`
- Extension: `extension`
- Category: `category`
- Missing-state: `missing`

Stage 4A only returns `.max` rows where `missing = 0`, and by default also verifies
that the file exists on disk.

Run:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.t2_catalog_stage4a_smoke

Optional search:

    python -m forest_manager.app.t2_catalog_stage4a_smoke tree
    python -m forest_manager.app.t2_catalog_stage4a_smoke vegetation

The next Stage 4 step will take one returned `.max` path, merge it into 3ds Max,
identify the newly merged node(s), and connect the selected source to Forest Pack.
