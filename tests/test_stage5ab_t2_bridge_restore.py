from __future__ import annotations

from pathlib import Path

from forest_manager.t2_bridge import T2AssetCatalog, T2AssetCatalogError, T2AssetRecord


def test_t2_bridge_exports_catalog_types():
    assert T2AssetCatalog is not None
    assert T2AssetCatalogError is not None
    assert T2AssetRecord is not None


def test_catalog_can_be_constructed_without_existing_database(tmp_path: Path):
    catalog = T2AssetCatalog(
        db_path=tmp_path / "missing.db",
        settings_path=tmp_path / "missing.json",
    )
    assert catalog.search_max_assets("lavender") == []
    diagnostics = catalog.diagnostics()
    assert diagnostics["database_exists"] is False
    assert diagnostics["settings_exists"] is False
