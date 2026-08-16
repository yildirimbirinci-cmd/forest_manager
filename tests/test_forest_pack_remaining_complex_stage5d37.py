from __future__ import annotations

import importlib

from forest_manager.forest_control.service import (
    ForestControlError,
    ForestPackControlService,
    ForestProperty,
    ForestSnapshot,
)


def _snapshot() -> ForestSnapshot:
    return ForestSnapshot(
        "FM_Test",
        3,
        {"read_only": 1, "scalar": 2, "color": 0},
        (
            ForestProperty("anim_time", "Time", "scalar", True, 160),
            ForestProperty("density_map", "Bitmaptexture", "scalar", True, "map"),
            ForestProperty("falloff_curve", "CurveControl", "read_only", True, "curve"),
        ),
        (),
    )


def test_inventory_exposes_discovered_property_metadata(monkeypatch):
    service = ForestPackControlService()
    monkeypatch.setattr(service, "discover", lambda preflight=True: (_snapshot(),))
    inventory = service.inventory("FM_Test")
    assert inventory["property_count"] == 3
    assert [p["value_class"] for p in inventory["properties"]] == ["Time", "Bitmaptexture", "CurveControl"]


def test_curve_metadata_is_read_only(monkeypatch):
    service = ForestPackControlService()
    monkeypatch.setattr(service, "discover", lambda preflight=True: (_snapshot(),))
    metadata = service.curve_metadata("FM_Test", "falloff_curve")
    assert metadata["value_class"] == "CurveControl"
    assert metadata["write_mode"] == "read_only"


def test_curve_metadata_rejects_non_curve(monkeypatch):
    service = ForestPackControlService()
    monkeypatch.setattr(service, "discover", lambda preflight=True: (_snapshot(),))
    try:
        service.curve_metadata("FM_Test", "anim_time")
    except ForestControlError as exc:
        assert "not CurveControl" in str(exc)
    else:
        raise AssertionError("Expected ForestControlError")


def test_stage5d37_classification_and_policy(monkeypatch, capsys):
    module = importlib.import_module("forest_manager.app.forest_pack_remaining_complex_stage5d37")

    class FakeService:
        def list_forests(self):
            return ("FM_Test",)

        def inventory(self, forest_name):
            return {
                "properties": [
                    {"name": "anim_time", "value_class": "Time"},
                    {"name": "density_map", "value_class": "Bitmaptexture"},
                    {"name": "falloff_curve", "value_class": "CurveControl"},
                ]
            }

        def curve_metadata(self, forest_name, name):
            return {"name": name, "value_class": "CurveControl", "write_mode": "read_only"}

    monkeypatch.setattr(module, "ForestPackControlService", FakeService)
    assert module.main() == 0
    output = capsys.readouterr().out
    assert '"Time": 1' in output
    assert '"Bitmaptexture": 1' in output
    assert '"CurveControl": 1' in output
    assert '"curve_control_write": false' in output
    assert "Stage 5D.37 remaining complex property discovery passed." in output
