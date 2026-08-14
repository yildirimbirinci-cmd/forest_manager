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
                "Lavandula angustifolia 'Hidcote' (Lavender)",
                r"C:\T2\Lavandula angustifolia\Lavandula angustifolia.max",
            ),
            FakeAsset(
                "Butomus umbellatus (Flowering rush)",
                r"C:\T2\Butomus\Butomus umbellatus.max",
            ),
            FakeAsset(
                "Rudbeckia 'Goldsturm' (Coneflower)",
                r"C:\T2\Rudbeckia\Rudbeckia Goldsturm.max",
            ),
            FakeAsset(
                "Bush_Berberis",
                r"C:\T2\Bush_Berberis\Bush_Berberis.max",
            ),
            FakeAsset(
                "Bush_Choisya",
                r"C:\T2\Bush_Choisya\Bush_Choisya.max",
            ),
        ]

    def search_max_assets(self, query, *, limit=20, require_existing_file=True):
        q = query.casefold()
        return [
            asset for asset in self.assets
            if q in asset.name.casefold()
        ][:limit]


def test_variants_are_term_scoped():
    assert terms_mod.variants_for_term("lavender") == ("lavender", "lavandula")
    assert terms_mod.variants_for_term("lily") == ("lily", "lilium")
    assert terms_mod.variants_for_term("shrub") == ("shrub", "bush")


def test_lily_cannot_use_shrub_synonym():
    report = matcher_mod.T2SemanticAssetMatcher(FakeCatalog()).match_text(
        "PLANTS: lily"
    )
    assert report.matches == ()
    assert report.unmatched_terms == ("lily",)


def test_shrub_can_match_bush_assets():
    report = matcher_mod.T2SemanticAssetMatcher(FakeCatalog()).match_text(
        "PLANTS: shrub"
    )
    assert report.matches
    assert all(item.source_term == "shrub" for item in report.matches)
    assert any(item.asset_name == "Bush_Berberis" for item in report.matches)


def test_realistic_stage5a_observation_keeps_sources_correct():
    report = matcher_mod.T2SemanticAssetMatcher(FakeCatalog()).match_text(
        "PLANTS: lavender purple white lillies flowers shrubs plants."
    )

    by_source = {}
    for item in report.matches:
        by_source.setdefault(item.source_term, []).append(item.asset_name)

    assert "lavender" in by_source
    assert "flower" in by_source
    assert "shrub" in by_source
    assert "lily" not in by_source
    assert "lily" in report.unmatched_terms

    for item in report.matches:
        if item.source_term == "lily":
            raise AssertionError("lily must never match a bush asset")


def test_matcher_never_returns_non_max():
    class BadCatalog:
        def search_max_assets(self, query, *, limit=20, require_existing_file=True):
            return [FakeAsset("Bush_Berberis", r"C:\T2\Bush_Berberis.obj")]

    report = matcher_mod.T2SemanticAssetMatcher(BadCatalog()).match_text(
        "PLANTS: shrub"
    )
    assert report.matches == ()
