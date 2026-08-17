from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_plant_groups():
    path = ROOT / "src" / "forest_manager" / "ui" / "plant_groups.py"
    spec = importlib.util.spec_from_file_location("stage716_plant_groups", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_bridge_identity_and_manifest_contract():
    bridge = (ROOT / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    runtime = (ROOT / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert '0.9.79' in bridge
    assert "stage8-versioned-bridge-no-watcher-20260817a" in bridge
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.79"' in runtime
    assert "FM_PLANT_GROUP_MANIFEST_GET" in bridge
    assert "FM_PLANT_GROUP_MANIFEST_SET" in bridge
    assert "ForestManagerPlantGroupManifest" in bridge
    assert "read_plant_group_manifest" in runtime
    assert "write_plant_group_manifest" in runtime


def test_reference_layer_is_canonicalized_and_hidden():
    bridge = (ROOT / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    assert 'getOrCreateManagedChildLayer "FM_REFERENCES"' in bridge
    assert 'setLayerProtectionState referencesLayer true true false' in bridge
    assert '__FM_CASE_RENAME__' in bridge


def test_manifest_groups_survive_after_legacy_forests_are_removed():
    module = _load_plant_groups()
    manifest = {
        "primary_forest": "FM_Forest_001",
        "groups": [
            {
                "group_id": "plant_group:1:FM_Layer_01_foreground_mass",
                "label": "Foreground Mass",
                "order": 1,
                "legacy_forest_name": "FM_Layer_01_foreground_mass",
                "source_names": ["Lavender"],
                "spacing_system": [7500.0, 7500.0],
                "area_nodes": ["Line001"],
            }
        ],
    }
    groups = module.discover_plant_groups(["FM_Forest_001"], manifest)
    assert len(groups) == 1
    assert groups[0].forest_name == "FM_Forest_001"
    assert groups[0].source_names == ("Lavender",)
    assert groups[0].spacing_system == (7500.0, 7500.0)
    assert groups[0].area_nodes == ("Line001",)


def test_destructive_migration_requires_explicit_spacing_acceptance():
    source = (ROOT / "src" / "forest_manager" / "forest_control" / "plant_group_migration.py").read_text(encoding="utf-8")
    assert "allow_spacing_semantic_only: bool = False" in source
    assert "if plan.representational_warning and not allow_spacing_semantic_only" in source
    assert "write_plant_group_manifest(manifest)" in source
    assert "readback_manifest != manifest" in source
    assert "delete_managed_forest(name)" in source
    assert source.index("write_plant_group_manifest(manifest)") < source.index("delete_managed_forest(name)")
    assert "missing_ownership" in source


def test_manifest_is_json_native_before_bridge_roundtrip():
    source = (ROOT / "src" / "forest_manager" / "forest_control" / "plant_group_migration.py").read_text(encoding="utf-8")
    assert 'item["source_names"] = list(group.source_names)' in source
    assert 'item["spacing_system"] = list(group.spacing_system)' in source
    assert 'item["area_nodes"] = list(group.area_nodes)' in source
    assert 'item["area_modes"] = list(group.area_modes)' in source
