from __future__ import annotations

import base64
import math
from pathlib import Path

import pytest

import forest_manager.forest_control.service as service_module
from forest_manager.forest_control.service import ForestControlError, ForestPackControlService


class FakePoint3Bridge:
    def __init__(self):
        self.arrays = {
            ("FM_Forest_001", "coloridlist"): [([148.0, 177.0, 27.0], "Point3")],
            ("FM_Forest_001", "ScaleList"): [(100.0, "Float")],
            ("FM_Forest_001", "cobjlist"): [("$CoronaProxy:Lavandula", "CProxy")],
        }

    @staticmethod
    def _decode(token: str) -> str:
        return base64.b64decode(token.encode("ascii")).decode("utf-8")

    def send(self, command: str):
        parts = command.split("|")
        if parts[0] == "FOREST_CONTROL_GET_ARRAY_ELEMENT":
            forest = self._decode(parts[1])
            prop = self._decode(parts[2])
            index = int(parts[3])
            values = self.arrays[(forest, prop)]
            if index < 0 or index >= len(values):
                return {"ok": False, "error": "index out of range"}
            value, value_class = values[index]
            if value_class == "Point3":
                return {"ok": True, "data": {
                    "forest_name": forest, "property_name": prop, "index": index,
                    "count": len(values), "value_class": "Point3", "scalar_type": "",
                    "vector_type": "point3", "value": list(value), "verified": True,
                }}
            if value_class == "Float":
                return {"ok": True, "data": {
                    "forest_name": forest, "property_name": prop, "index": index,
                    "count": len(values), "value_class": "Float", "scalar_type": "float",
                    "vector_type": "", "value": value, "verified": True,
                }}
            return {"ok": False, "error": f"not writable by verified endpoint: {value_class}"}
        if parts[0] == "FOREST_CONTROL_SET_ARRAY_POINT3":
            forest = self._decode(parts[1])
            prop = self._decode(parts[2])
            index = int(parts[3])
            values = self.arrays[(forest, prop)]
            before, value_class = values[index]
            assert value_class == "Point3"
            value = [float(parts[4]), float(parts[5]), float(parts[6])]
            values[index] = (value, value_class)
            return {"ok": True, "data": {
                "forest_name": forest, "property_name": prop, "index": index,
                "count": len(values), "value_class": "Point3", "vector_type": "point3",
                "before_value": list(before), "after_value": list(value), "verified": True,
            }}
        if parts[0] == "FOREST_CONTROL_SET_ARRAY_SCALAR":
            forest = self._decode(parts[1])
            prop = self._decode(parts[2])
            index = int(parts[3])
            values = self.arrays[(forest, prop)]
            before, value_class = values[index]
            value = float(self._decode(parts[5]))
            values[index] = (value, value_class)
            return {"ok": True, "data": {
                "forest_name": forest, "property_name": prop, "index": index,
                "count": len(values), "value_class": value_class, "scalar_type": "float",
                "before_value": before, "after_value": value, "verified": True,
            }}
        raise AssertionError(command)


@pytest.fixture()
def bridge(monkeypatch):
    fake = FakePoint3Bridge()
    monkeypatch.setattr(service_module, "ensure_current_bridge", lambda: {"ok": True})
    monkeypatch.setattr(service_module, "send_command", fake.send)
    return fake


def test_point3_array_write_readback_and_rollback(bridge):
    service = ForestPackControlService()
    before = list(bridge.arrays[("FM_Forest_001", "coloridlist")][0][0])
    result = service.set_array_element("FM_Forest_001", "coloridlist", 0, [149, 177, 27])
    assert result["verified"] is True
    assert result["vector_type"] == "point3"
    assert result["after_value"] == [149.0, 177.0, 27.0]
    rollback = service.rollback()
    assert len(rollback) == 1
    assert rollback[0]["index"] == 0
    assert bridge.arrays[("FM_Forest_001", "coloridlist")][0][0] == before


def test_point3_validation_rejects_wrong_shape_type_and_nonfinite(bridge):
    service = ForestPackControlService()
    with pytest.raises(ForestControlError, match="exactly 3"):
        service.set_array_element("FM_Forest_001", "coloridlist", 0, [1, 2])
    with pytest.raises(ForestControlError, match="numeric"):
        service.set_array_element("FM_Forest_001", "coloridlist", 0, [1, "x", 3])
    with pytest.raises(ForestControlError, match="finite"):
        service.set_array_element("FM_Forest_001", "coloridlist", 0, [1, math.inf, 3])
    with pytest.raises(ForestControlError, match="finite"):
        service.set_array_element("FM_Forest_001", "coloridlist", 0, [1, math.nan, 3])
    assert service.rollback() == []


def test_reference_arrays_remain_blocked(bridge):
    service = ForestPackControlService()
    with pytest.raises(ForestControlError, match="FOREST_CONTROL_GET_ARRAY_ELEMENT failed"):
        service.set_array_element("FM_Forest_001", "cobjlist", 0, [1, 2, 3])
    assert service.rollback() == []


def test_mixed_array_scalar_and_point3_journal_rolls_back(bridge):
    service = ForestPackControlService()
    scale_before = bridge.arrays[("FM_Forest_001", "ScaleList")][0][0]
    point_before = list(bridge.arrays[("FM_Forest_001", "coloridlist")][0][0])
    service.set_array_element("FM_Forest_001", "ScaleList", 0, scale_before + 1.0)
    service.set_array_element("FM_Forest_001", "coloridlist", 0, [149, 177, 27])
    rollback = service.rollback()
    assert len(rollback) == 2
    assert bridge.arrays[("FM_Forest_001", "ScaleList")][0][0] == scale_before
    assert bridge.arrays[("FM_Forest_001", "coloridlist")][0][0] == point_before


def test_stage64_bridge_contract_and_stable_startup_loader():
    root = Path(__file__).resolve().parents[1]
    bridge_text = (root / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    runtime_text = (root / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert "FOREST_CONTROL_SET_ARRAY_POINT3" in bridge_text
    assert "fn forestControlSetArrayPoint3Json" in bridge_text
    assert "stage6-6-material-reference-write-20260816a" in bridge_text
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage6-6-material-reference-write-20260816a"' in runtime_text
    assert "catch (throw" not in bridge_text
    loader_section = runtime_text.split("def _startup_loader_text", 1)[1].split("def install_startup_bridge_loader", 1)[0]
    assert "EXPECTED_BRIDGE_BUILD_ID" not in loader_section
    assert "ForestManager_Bridge.ms" not in loader_section
