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
for package in ("asset_matching", "placement"):
    mod = types.ModuleType("forest_manager." + package)
    mod.__path__ = [str(SRC / package)]
    sys.modules.setdefault("forest_manager." + package, mod)

_load("forest_manager.asset_matching.semantic_terms", SRC / "asset_matching" / "semantic_terms.py")
matcher_mod = _load("forest_manager.asset_matching.t2_asset_matcher", SRC / "asset_matching" / "t2_asset_matcher.py")
service_mod = _load("forest_manager.placement.matched_asset_service", SRC / "placement" / "matched_asset_service.py")

@dataclass
class Asset:
    name: str
    file_path: str

class Catalog:
    assets = [
        Asset("Lavandula angustifolia (Lavender)", r"C:\\T2\\Lavender.max"),
        Asset("Rudbeckia Goldsturm (Coneflower)", r"C:\\T2\\Rudbeckia.max"),
        Asset("Bush_Berberis", r"C:\\T2\\Bush_Berberis.max"),
    ]
    def search_max_assets(self, query, *, limit=20, require_existing_file=True):
        q=query.casefold()
        return [a for a in self.assets if q in a.name.casefold()][:limit]

@dataclass
class Response:
    ok: bool=True
    data: dict=None
    error: str=""
    def __post_init__(self):
        if self.data is None: self.data={}

class Client:
    def __init__(self):
        self.paths=[]
        self.probs=[]
        self.reset_calls=0
    def ping(self): return Response(data={"bridge_version":"0.9.0"})
    def reset_managed_forest_from_selection(self):
        self.reset_calls += 1
        return Response(data={"forest_name":"FM_Forest_001","verified":True})
    def append_t2_asset_geometry(self,path,probability=50.0):
        self.paths.append(path); self.probs.append(probability)
        return Response(data={"asset_path":path,"verified":True})
    def set_geometry_probabilities(self,probabilities):
        self.probs=list(probabilities)
        return Response(data={"probabilities":list(probabilities),"probability_total":sum(probabilities),"verified":True})
    def configure_fixed_distribution_units(self):
        return Response(data={"units_x":45000.0,"units_y":45000.0,"maxdensity":10,"verified":True})
    def normalize_reference_sources(self):
        return Response(data={"layer_name":"FM_References","layer_visible":False,"target_z_mm":-1500.0,"verified":True})
    def get_forest_geometry_summary(self):
        return Response(data={"geometry_names":[Path(p).stem for p in self.paths]})


def build():
    return service_mod.MatchedAssetForestService(
        matcher_mod.T2SemanticAssetMatcher(Catalog()), Client()
    )


def test_preview_selects_one_best_asset_per_semantic_term():
    service=build()
    result=service.preview("PLANTS: lavender flowers shrubs plants.")
    selected=result["selected_assets"]
    assert [x["source_term"] for x in selected] == ["lavender","flower","shrub"]
    assert len(selected)==3
    assert all(abs(x["probability"]-33.333333)<0.001 for x in selected)


def test_apply_uses_exact_matched_t2_paths_and_resets_managed_forest():
    service=build()
    result=service.apply("PLANTS: lavender flowers shrubs plants.")
    assert result["verified"] is True
    assert service.client.reset_calls == 1
    assert service.client.paths == [
        r"C:\\T2\\Lavender.max",
        r"C:\\T2\\Rudbeckia.max",
        r"C:\\T2\\Bush_Berberis.max",
    ]
    assert abs(sum(service.client.probs)-100.0)<0.001


def test_unmatched_lily_is_not_substituted():
    service=build()
    result=service.preview("PLANTS: lily lavender")
    assert [x["source_term"] for x in result["selected_assets"]] == ["lavender"]
    assert "lily" in result["match_report"]["unmatched_terms"]


def test_maxscript_reset_command_is_local_to_managed_forest():
    source=(ROOT/"maxscripts"/"ForestManager_Bridge.ms").read_text(encoding="utf-8")
    assert '"RESET_MANAGED_FOREST_FROM_SELECTION"' in source
    assert '0.9.0' in source
    assert 'getNodeByName "FM_Forest_001"' in source
    assert 'FM_Forest_001 exists but is not a Forest Pack object. Refusing to delete it.' in source


def test_fixed_distribution_baseline_is_preserved():
    source=(ROOT/"maxscripts"/"ForestManager_Bridge.ms").read_text(encoding="utf-8")
    assert "forestNode.units_x = 45000.0" in source
    assert "forestNode.units_y = 45000.0" in source
    assert "forestNode.maxdensity = 10" in source
