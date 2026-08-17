from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_plant_groups_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "src" / "forest_manager" / "ui" / "plant_groups.py"
    spec = importlib.util.spec_from_file_location("fm_stage717_plant_groups", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_groups_share_single_runtime_forest_and_keep_group_values():
    module = _load_plant_groups_module()
    manifest = {
        "primary_forest": "FM_Forest_001",
        "groups": [
            {
                "group_id": "plant_group:1:foreground",
                "label": "Foreground Mass",
                "order": 1,
                "source_names": ["Lavandula"],
                "spacing_system": [7500.0, 7500.0],
                "area_nodes": ["Line001"],
                "artist_values": {"naturalness": "Natural"},
            },
            {
                "group_id": "plant_group:2:accent",
                "label": "Mid Accent",
                "order": 2,
                "source_names": ["Butomus"],
                "spacing_system": [2500.0, 2500.0],
                "area_nodes": ["Line001"],
                "artist_values": {"cluster_character": "Soft Clusters"},
            },
        ],
    }
    groups = module.discover_plant_groups(["FM_Forest_001"], manifest)
    assert [g.label for g in groups] == ["Foreground Mass", "Mid Accent"]
    assert {g.forest_name for g in groups} == {"FM_Forest_001"}
    assert groups[0].spacing_system == (7500.0, 7500.0)
    assert groups[0].artist_values["naturalness"] == "Natural"
    assert groups[1].artist_values["cluster_character"] == "Soft Clusters"
    assert all(g.manifest_backed for g in groups)


def test_controller_contains_manifest_scoped_artist_persistence_contract():
    root = Path(__file__).resolve().parents[1]
    controller = (root / "src" / "forest_manager" / "ui" / "controller.py").read_text(encoding="utf-8")
    compile(controller, "controller.py", "exec")
    assert "write_plant_group_manifest" in controller
    assert "_persist_group_artist_control" in controller
    assert "group.manifest_backed" in controller
    assert "selected_group_id=group.group_id" in controller
    assert "target[\"spacing_system\"] = [raw_spacing, raw_spacing]" in controller
