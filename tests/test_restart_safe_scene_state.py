from __future__ import annotations

from forest_manager.ui.controller import ForestManagerUIController
from forest_manager.ui.plant_groups import PlantGroupTarget


def _group(group_id: str, spacing: float) -> PlantGroupTarget:
    return PlantGroupTarget(
        group_id=group_id,
        label=group_id,
        forest_name="FM_Forest_001",
        order=1,
        source_names=(group_id,),
        spacing_system=(spacing, spacing),
        manifest_backed=True,
    )


def test_runtime_cache_is_rebuilt_from_current_manifest_without_stale_groups():
    controller = ForestManagerUIController.__new__(ForestManagerUIController)
    controller._group_runtime_cache = {
        "old_scene_group": {"source_names": ["Old"], "spacing": 999.0}
    }
    controller._state = type(
        "_State",
        (),
        {"scene_units": {"display_unit": "meters", "one_meter_system_units": 100.0,
                         "one_centimeter_system_units": 1.0, "one_millimeter_system_units": 0.1}},
    )()

    group = _group("new_scene_group", 7500.0)
    manifest = {
        "primary_forest": "FM_Forest_001",
        "groups": [{
            "group_id": "new_scene_group",
            "source_names": ["Lavender"],
            "spacing_system": [7500.0, 7500.0],
            "artist_values": {},
        }],
    }

    controller._prime_group_runtime_cache(
        manifest,
        (group,),
        scene_units={
            "display_unit": "meters",
            "one_meter_system_units": 100.0,
            "one_centimeter_system_units": 1.0,
            "one_millimeter_system_units": 0.1,
        },
    )

    assert "old_scene_group" not in controller._group_runtime_cache
    assert set(controller._group_runtime_cache) == {"new_scene_group"}
    assert controller._group_runtime_cache["new_scene_group"]["spacing"] == 75.0
    assert controller._group_runtime_cache["new_scene_group"]["spacing_suffix"] == "m"


def test_restart_contract_keeps_pending_state_non_persistent():
    source = __import__("pathlib").Path(__file__).resolve().parents[1] / "src" / "forest_manager" / "ui" / "controller.py"
    text = source.read_text(encoding="utf-8")

    assert "self._pending: dict[str, PendingEdit] = {}" in text
    assert "self._group_runtime_cache: dict[str, dict[str, Any]] = {}" in text
    assert "self._pending.clear()" in text
    assert "pending_edits=()" in text
    assert "self._group_runtime_cache.clear()" in text
