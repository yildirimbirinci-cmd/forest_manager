from __future__ import annotations

import base64

import pytest

import forest_manager.forest_control.service as service_module
from forest_manager.forest_control.service import ForestControlError, ForestPackControlService


class FakeColorBridge:
    def __init__(self):
        self.values = {
            ("FM_Forest_001", "tintcolor1"): ([32.0, 64.0, 96.0], "Color", "color"),
            ("FM_Forest_001", "seed"): (123456, "Integer", "scalar"),
            ("FM_Forest_001", "cobjlist"): (None, "ArrayParameter", "read_only"),
        }

    @staticmethod
    def _decode(token: str) -> str:
        return base64.b64decode(token.encode("ascii")).decode("utf-8")

    def send(self, command: str):
        parts = command.split("|")
        if parts[0] == "FOREST_CONTROL_GET_PROPERTY":
            forest = self._decode(parts[1])
            prop = self._decode(parts[2])
            value, value_class, write_mode = self.values[(forest, prop)]
            return {
                "ok": True,
                "data": {
                    "forest_name": forest,
                    "property": {
                        "name": prop,
                        "value_class": value_class,
                        "write_mode": write_mode,
                        "readable": True,
                        "value": value,
                    },
                    "verified": True,
                },
            }
        if parts[0] == "FOREST_CONTROL_SET_COLOR":
            forest = self._decode(parts[1])
            prop = self._decode(parts[2])
            before, value_class, write_mode = self.values[(forest, prop)]
            assert value_class == "Color"
            assert write_mode == "color"
            value = [float(parts[3]), float(parts[4]), float(parts[5])]
            self.values[(forest, prop)] = (value, value_class, write_mode)
            return {
                "ok": True,
                "data": {
                    "forest_name": forest,
                    "property_name": prop,
                    "value_class": "Color",
                    "color_type": "rgb_0_255",
                    "before_value": before,
                    "after_value": value,
                    "verified": True,
                },
            }
        if parts[0] == "FOREST_CONTROL_SET_SCALAR":
            forest = self._decode(parts[1])
            prop = self._decode(parts[2])
            before, value_class, write_mode = self.values[(forest, prop)]
            value = int(self._decode(parts[4]))
            self.values[(forest, prop)] = (value, value_class, write_mode)
            return {
                "ok": True,
                "data": {
                    "forest_name": forest,
                    "property_name": prop,
                    "before_value": before,
                    "after_value": value,
                    "verified": True,
                },
            }
        raise AssertionError(command)


@pytest.fixture()
def bridge(monkeypatch):
    fake = FakeColorBridge()
    monkeypatch.setattr(service_module, "ensure_current_bridge", lambda: {"ok": True})
    monkeypatch.setattr(service_module, "send_command", fake.send)
    return fake


def test_color_write_readback_and_rollback(bridge):
    service = ForestPackControlService()
    before = list(bridge.values[("FM_Forest_001", "tintcolor1")][0])
    result = service.set_property("FM_Forest_001", "tintcolor1", [33, 65.5, 97])
    assert result["verified"] is True
    assert result["color_type"] == "rgb_0_255"
    assert result["after_value"] == [33.0, 65.5, 97.0]
    rollback = service.rollback()
    assert len(rollback) == 1
    assert bridge.values[("FM_Forest_001", "tintcolor1")][0] == before


def test_color_validation_rejects_bad_shape_type_and_range_without_write(bridge):
    service = ForestPackControlService()
    before = list(bridge.values[("FM_Forest_001", "tintcolor1")][0])
    with pytest.raises(ForestControlError, match="exactly 3"):
        service.set_property("FM_Forest_001", "tintcolor1", [1, 2])
    with pytest.raises(ForestControlError, match="numeric RGB"):
        service.set_property("FM_Forest_001", "tintcolor1", [1, "2", 3])
    with pytest.raises(ForestControlError, match="0..255"):
        service.set_property("FM_Forest_001", "tintcolor1", [1, 2, 256])
    assert bridge.values[("FM_Forest_001", "tintcolor1")][0] == before
    assert service.rollback() == []


def test_mixed_scalar_color_journal_rolls_back_in_reverse_order(bridge):
    service = ForestPackControlService()
    color_before = list(bridge.values[("FM_Forest_001", "tintcolor1")][0])
    seed_before = bridge.values[("FM_Forest_001", "seed")][0]
    service.set_property("FM_Forest_001", "seed", seed_before + 1)
    service.set_property("FM_Forest_001", "tintcolor1", [40, 70, 100])
    rollback = service.rollback()
    assert len(rollback) == 2
    assert bridge.values[("FM_Forest_001", "seed")][0] == seed_before
    assert bridge.values[("FM_Forest_001", "tintcolor1")][0] == color_before


def test_stage62_bridge_contract_and_stable_startup_loader():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    bridge_text = (root / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    runtime_text = (root / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert "FOREST_CONTROL_SET_COLOR" in bridge_text
    assert "fn forestControlSetColorJson" in bridge_text
    assert "stage6-3-array-scalar-write-20260816a" in bridge_text
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage6-3-array-scalar-write-20260816a"' in runtime_text
    loader_section = runtime_text.split("def _startup_loader_text", 1)[1].split("def install_startup_bridge_loader", 1)[0]
    assert "EXPECTED_BRIDGE_BUILD_ID" not in loader_section
    assert "ForestManager_Bridge.ms" not in loader_section
