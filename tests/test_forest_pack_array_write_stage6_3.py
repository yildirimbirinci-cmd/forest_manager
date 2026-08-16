from __future__ import annotations

import base64

import pytest

import forest_manager.forest_control.service as service_module
from forest_manager.forest_control.service import ForestControlError, ForestPackControlService


class FakeArrayBridge:
    def __init__(self):
        self.properties = {
            ("FM_Forest_001", "seed"): (123456, "Integer", "scalar"),
            ("FM_Forest_001", "tintcolor1"): ([32.0, 64.0, 96.0], "Color", "color"),
        }
        self.arrays = {
            ("FM_Forest_001", "ScaleList"): [(100.0, "Float")],
            ("FM_Forest_001", "geomlist"): [(2, "Integer")],
            ("FM_Forest_001", "usemeshdimlist"): [(False, "BooleanClass")],
            ("FM_Forest_001", "namelist"): [("Lavandula", "String")],
            ("FM_Forest_001", "cobjlist"): [("$CoronaProxy:Lavandula", "CProxy")],
        }

    @staticmethod
    def _decode(token: str) -> str:
        return base64.b64decode(token.encode("ascii")).decode("utf-8")

    @staticmethod
    def _scalar_type(value_class: str) -> str:
        return {
            "BooleanClass": "bool",
            "Integer": "int",
            "Float": "float",
            "String": "string",
        }.get(value_class, "")

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
            scalar_type = self._scalar_type(value_class)
            if not scalar_type:
                return {"ok": False, "error": f"not scalar writable: {value_class}"}
            return {
                "ok": True,
                "data": {
                    "forest_name": forest,
                    "property_name": prop,
                    "index": index,
                    "count": len(values),
                    "value_class": value_class,
                    "scalar_type": scalar_type,
                    "value": value,
                    "verified": True,
                },
            }
        if parts[0] == "FOREST_CONTROL_SET_ARRAY_SCALAR":
            forest = self._decode(parts[1])
            prop = self._decode(parts[2])
            index = int(parts[3])
            scalar_type = parts[4]
            text = self._decode(parts[5])
            values = self.arrays[(forest, prop)]
            before, value_class = values[index]
            expected = self._scalar_type(value_class)
            assert scalar_type == expected
            if scalar_type == "bool":
                value = text.lower() == "true"
            elif scalar_type == "int":
                value = int(text)
            elif scalar_type == "float":
                value = float(text)
            else:
                value = text
            values[index] = (value, value_class)
            return {
                "ok": True,
                "data": {
                    "forest_name": forest,
                    "property_name": prop,
                    "index": index,
                    "count": len(values),
                    "value_class": value_class,
                    "scalar_type": scalar_type,
                    "before_value": before,
                    "after_value": value,
                    "verified": True,
                },
            }
        if parts[0] == "FOREST_CONTROL_GET_PROPERTY":
            forest = self._decode(parts[1])
            prop = self._decode(parts[2])
            value, value_class, write_mode = self.properties[(forest, prop)]
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
        if parts[0] == "FOREST_CONTROL_SET_SCALAR":
            forest = self._decode(parts[1])
            prop = self._decode(parts[2])
            before, value_class, write_mode = self.properties[(forest, prop)]
            value = int(self._decode(parts[4]))
            self.properties[(forest, prop)] = (value, value_class, write_mode)
            return {"ok": True, "data": {"before_value": before, "after_value": value, "verified": True}}
        if parts[0] == "FOREST_CONTROL_SET_COLOR":
            forest = self._decode(parts[1])
            prop = self._decode(parts[2])
            before, value_class, write_mode = self.properties[(forest, prop)]
            value = [float(parts[3]), float(parts[4]), float(parts[5])]
            self.properties[(forest, prop)] = (value, value_class, write_mode)
            return {"ok": True, "data": {"before_value": before, "after_value": value, "verified": True}}
        raise AssertionError(command)


@pytest.fixture()
def bridge(monkeypatch):
    fake = FakeArrayBridge()
    monkeypatch.setattr(service_module, "ensure_current_bridge", lambda: {"ok": True})
    monkeypatch.setattr(service_module, "send_command", fake.send)
    return fake


def test_array_float_write_readback_and_rollback(bridge):
    service = ForestPackControlService()
    before = bridge.arrays[("FM_Forest_001", "ScaleList")][0][0]
    result = service.set_array_element("FM_Forest_001", "ScaleList", 0, 101.0)
    assert result["verified"] is True
    assert result["scalar_type"] == "float"
    assert result["after_value"] == 101.0
    rollback = service.rollback()
    assert len(rollback) == 1
    assert rollback[0]["index"] == 0
    assert bridge.arrays[("FM_Forest_001", "ScaleList")][0][0] == before


def test_array_primitive_types_are_supported(bridge):
    service = ForestPackControlService()
    service.set_array_element("FM_Forest_001", "geomlist", 0, 3)
    service.set_array_element("FM_Forest_001", "usemeshdimlist", 0, True)
    service.set_array_element("FM_Forest_001", "namelist", 0, "Lavandula Updated")
    assert bridge.arrays[("FM_Forest_001", "geomlist")][0][0] == 3
    assert bridge.arrays[("FM_Forest_001", "usemeshdimlist")][0][0] is True
    assert bridge.arrays[("FM_Forest_001", "namelist")][0][0] == "Lavandula Updated"
    assert len(service.rollback()) == 3


def test_array_index_and_reference_guards(bridge):
    service = ForestPackControlService()
    with pytest.raises(ForestControlError, match="zero or greater"):
        service.set_array_element("FM_Forest_001", "ScaleList", -1, 101.0)
    with pytest.raises(ForestControlError, match="integer"):
        service.set_array_element("FM_Forest_001", "ScaleList", True, 101.0)
    with pytest.raises(ForestControlError, match="not scalar writable"):
        service.set_array_element("FM_Forest_001", "cobjlist", 0, "x")
    assert service.rollback() == []


def test_mixed_scalar_color_array_journal_rolls_back_in_reverse_order(bridge):
    service = ForestPackControlService()
    seed_before = bridge.properties[("FM_Forest_001", "seed")][0]
    color_before = list(bridge.properties[("FM_Forest_001", "tintcolor1")][0])
    scale_before = bridge.arrays[("FM_Forest_001", "ScaleList")][0][0]
    service.set_property("FM_Forest_001", "seed", seed_before + 1)
    service.set_property("FM_Forest_001", "tintcolor1", [40, 70, 100])
    service.set_array_element("FM_Forest_001", "ScaleList", 0, scale_before + 1.0)
    rollback = service.rollback()
    assert len(rollback) == 3
    assert bridge.properties[("FM_Forest_001", "seed")][0] == seed_before
    assert bridge.properties[("FM_Forest_001", "tintcolor1")][0] == color_before
    assert bridge.arrays[("FM_Forest_001", "ScaleList")][0][0] == scale_before


def test_stage63_bridge_contract_and_stable_startup_loader():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    bridge_text = (root / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    runtime_text = (root / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert "FOREST_CONTROL_GET_ARRAY_ELEMENT" in bridge_text
    assert "FOREST_CONTROL_SET_ARRAY_SCALAR" in bridge_text
    assert "fn forestControlSetArrayScalarJson" in bridge_text
    assert "stage6-5-node-reference-write-20260816a" in bridge_text
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage6-5-node-reference-write-20260816a"' in runtime_text
    loader_section = runtime_text.split("def _startup_loader_text", 1)[1].split("def install_startup_bridge_loader", 1)[0]
    assert "EXPECTED_BRIDGE_BUILD_ID" not in loader_section
    assert "ForestManager_Bridge.ms" not in loader_section
