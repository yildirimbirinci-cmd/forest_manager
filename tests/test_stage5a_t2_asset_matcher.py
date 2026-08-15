from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import importlib.util
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "forest_manager"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


forest_pkg = types.ModuleType("forest_manager")
forest_pkg.__path__ = [str(SRC)]
sys.modules.setdefault("forest_manager", forest_pkg)

matching_pkg = types.ModuleType("forest_manager.asset_matching")
matching_pkg.__path__ = [str(SRC / "asset_matching")]
sys.modules.setdefault("forest_manager.asset_matching", matching_pkg)

terms_mod = _load(
    "forest_manager.asset_matching.semantic_terms",
    SRC / "asset_matching" / "semantic_terms.py",
)
matcher_mod = _load(
    "forest_manager.asset_matching.t2_asset_matcher",
    SRC / "asset_matching" / "t2_asset_matcher.py",
)


@dataclass
class FakeAsset:
    name: str
    file_path: str


class FakeCatalog:
    def __init__(self):
        self.assets = [
            FakeAsset(
                "Acer campestre (Field maple)",
                r"C:\T2\Acer campestre (Field maple)\Acer campestre (Field maple).max",
            ),
            FakeAsset(
                "Alnus glutinosa (Black alder)",
                r"C:\T2\Alnus glutinosa (Black alder)\Alnus glutinosa (Black alder).max",
            ),
            FakeAsset(
                "Lavandula angustifolia",
                r"C:\T2\Lavandula angustifolia\Lavandula angustifolia.max",
            ),
        ]

    def search_max_assets(self, query, *, limit=20, require_existing_file=True):
        q = query.casefold()
        return [
            asset for asset in self.assets
            if q in asset.name.casefold()
        ][:limit]


def test_extracts_partial_plants_output():
    result = terms_mod.extract_semantic_search_terms(
        "PLANTS: lavender purple white lillies flowers shrubs plants."
    )
    assert "lavender" in result.terms
    assert "lily" in result.terms
    assert "plant" not in result.terms
    assert "purple" not in result.terms


def test_botanical_synonym_is_added():
    result = terms_mod.extract_semantic_search_terms("field maple alder")
    assert "acer" in result.query_variants
    assert "alnus" in result.query_variants


def test_matcher_returns_only_real_catalog_assets():
    report = matcher_mod.T2SemanticAssetMatcher(FakeCatalog()).match_text(
        "PLANTS: lavender; alder; field maple"
    )
    names = [item.asset_name for item in report.matches]
    assert "Lavandula angustifolia" in names
    assert "Alnus glutinosa (Black alder)" in names
    assert "Acer campestre (Field maple)" in names


def test_no_match_does_not_invent_asset():
    report = matcher_mod.T2SemanticAssetMatcher(FakeCatalog()).match_text(
        "PLANTS: bamboo palm cycad"
    )
    assert report.matches == ()
    assert set(report.unmatched_terms) == {"bamboo", "palm", "cycad"}


def test_non_max_records_are_rejected():
    class BadCatalog:
        def search_max_assets(self, query, *, limit=20, require_existing_file=True):
            return [FakeAsset("Acer campestre", r"C:\T2\acer.obj")]

    report = matcher_mod.T2SemanticAssetMatcher(BadCatalog()).match_text("maple")
    assert report.matches == ()
