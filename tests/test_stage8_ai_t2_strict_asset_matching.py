from pathlib import Path

import pytest

from forest_manager.forest_control.stage8_asset_resolution import Stage8AssetResolutionError, Stage8T2AssetResolver
from forest_manager.t2_bridge.catalog import T2AssetRecord


def _record(name: str, path: str) -> T2AssetRecord:
    return T2AssetRecord(id=1, name=name, file_path=Path(path), folder_path=Path(path).parent, extension=".max", category="Plants", missing=False, source="library_scan")


class FakeCatalog:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def search_max_assets(self, term, limit=100, require_existing_file=True):
        self.queries.append(term)
        return list(self.rows.get(term.casefold(), ()))

    def diagnostics(self):
        return {"database": None, "library_roots": ["C:/T2"]}


def test_strict_ai_resolution_uses_requested_lexical_fallback_not_role_alias():
    coneflower = _record("Rudbeckia 'Goldsturm' (Coneflower)", "C:/T2/Rudbeckia 'Goldsturm' (Coneflower).max")
    berberis = _record("Bush_Berberis", "C:/T2/Bush_Berberis.max")
    catalog = FakeCatalog({"purple coneflower": (), "coneflower": (coneflower,), "purple": (), "bush_berberis": (berberis,), "berberis": (berberis,)})
    resolver = Stage8T2AssetResolver(catalog=catalog, control_service=object())
    resolved = resolver.resolve_asset_strict("purple coneflower", "structural_shrub")
    assert resolved.name == "Rudbeckia 'Goldsturm' (Coneflower)"
    assert "Bush_Berberis" not in catalog.queries
    assert "Berberis" not in catalog.queries


def test_strict_ai_resolution_singularizes_plural_common_name():
    rosa = _record("Rosa canina (Dog rose)", "C:/T2/Rosa canina (Dog rose).max")
    rosemary = _record("Rosmarinus officinalis (Rosemary)", "C:/T2/Rosmarinus officinalis (Rosemary).max")
    catalog = FakeCatalog({"roses": (), "rose": (rosa, rosemary)})
    resolver = Stage8T2AssetResolver(catalog=catalog, control_service=object())
    resolved = resolver.resolve_asset_strict("roses", "flower_accent")
    assert resolved.name == "Rosa canina (Dog rose)"


def test_strict_ai_resolution_rejects_unrelated_role_alias_when_requested_name_has_no_match():
    berberis = _record("Bush_Berberis", "C:/T2/Bush_Berberis.max")
    catalog = FakeCatalog({"japanese maple": (), "japanese": (), "maple": (), "bush_berberis": (berberis,), "berberis": (berberis,)})
    resolver = Stage8T2AssetResolver(catalog=catalog, control_service=object())
    with pytest.raises(Stage8AssetResolutionError):
        resolver.resolve_asset_strict("Japanese maple", "structural_shrub")
    assert "Bush_Berberis" not in catalog.queries
    assert "Berberis" not in catalog.queries


def test_strict_ai_resolution_rejects_tree_asset_for_structural_shrub_role():
    maple = _record(
        "Acer campestre 'Streetwise' (Field maple cultivar )",
        "C:/T2/Asset Library/3D/03_VEGETATIONS/01_Trees/Acer campestre/Acer campestre.max",
    )
    catalog = FakeCatalog({"japanese maple": (), "japanese": (), "maple": (maple,)})
    resolver = Stage8T2AssetResolver(catalog=catalog, control_service=object())
    with pytest.raises(Stage8AssetResolutionError, match="semantic asset category compatibility"):
        resolver.resolve_asset_strict("Japanese maple", "structural_shrub")


def test_strict_ai_resolution_allows_tree_asset_for_tree_canopy_role():
    maple = _record(
        "Acer campestre 'Streetwise' (Field maple cultivar )",
        "C:/T2/Asset Library/3D/03_VEGETATIONS/01_Trees/Acer campestre/Acer campestre.max",
    )
    catalog = FakeCatalog({"japanese maple": (), "japanese": (), "maple": (maple,)})
    resolver = Stage8T2AssetResolver(catalog=catalog, control_service=object())
    resolved = resolver.resolve_asset_strict("Japanese maple", "tree_canopy")
    assert resolved.name.startswith("Acer campestre")


def test_strict_ai_resolution_allows_plant_asset_for_flower_role():
    coneflower = _record(
        "Rudbeckia 'Goldsturm' (Coneflower)",
        "C:/T2/Asset Library/3D/03_VEGETATIONS/02_Plants/Rudbeckia/Rudbeckia.max",
    )
    catalog = FakeCatalog({"purple coneflower": (), "coneflower": (coneflower,), "purple": ()})
    resolver = Stage8T2AssetResolver(catalog=catalog, control_service=object())
    resolved = resolver.resolve_asset_strict("purple coneflower", "flower_accent")
    assert resolved.name == "Rudbeckia 'Goldsturm' (Coneflower)"
