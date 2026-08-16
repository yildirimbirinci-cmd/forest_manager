from __future__ import annotations

import base64
from pathlib import Path

import pytest

import forest_manager.forest_control.service as service_module
from forest_manager.forest_control.service import ForestControlError, ForestPackControlService


class FakeNodeReferenceBridge:
    def __init__(self):
        self.arrays = {
            ("FM_Forest_001", "arnodelist"): [(None, "UndefinedClass"), ("Line001", "line")],
            ("FM_Forest_001", "cobjlist"): [("Lavandula", "CProxy")],
            ("FM_Forest_001", "ScaleList"): [(100.0, "Float")],
            ("FM_Forest_001", "coloridlist"): [([148.0, 177.0, 27.0], "Point3")],
        }
        self.scene_nodes = {"Line001", "FM_Forest_001"}

    @staticmethod
    def _decode(token: str) -> str:
        return base64.b64decode(token.encode("ascii")).decode("utf-8")

    def send(self, command: str):
        parts = command.split("|")
        op = parts[0]
        if op == "FOREST_CONTROL_GET_ARRAY_ELEMENT":
            forest = self._decode(parts[1])
            prop = self._decode(parts[2])
            index = int(parts[3])
            values = self.arrays[(forest, prop)]
            value, value_class = values[index]
            if prop == "arnodelist":
                return {"ok": True, "data": {
                    "forest_name": forest, "property_name": prop, "index": index,
                    "count": len(values), "value_class": value_class,
                    "scalar_type": "", "vector_type": "", "reference_type": "node",
                    "value": value, "verified": True,
                }}
            if value_class == "Float":
                return {"ok": True, "data": {
                    "forest_name": forest, "property_name": prop, "index": index,
                    "count": len(values), "value_class": value_class,
                    "scalar_type": "float", "vector_type": "", "reference_type": "",
                    "value": value, "verified": True,
                }}
            if value_class == "Point3":
                return {"ok": True, "data": {
                    "forest_name": forest, "property_name": prop, "index": index,
                    "count": len(values), "value_class": value_class,
                    "scalar_type": "", "vector_type": "point3", "reference_type": "",
                    "value": list(value), "verified": True,
                }}
            return {"ok": False, "error": f"not writable by a verified endpoint: {value_class}"}
        if op == "FOREST_CONTROL_SET_ARRAY_NODE_REF":
            forest = self._decode(parts[1])
            prop = self._decode(parts[2])
            index = int(parts[3])
            mode = parts[4]
            token = parts[5]
            if prop != "arnodelist":
                return {"ok": False, "error": "Node reference array writes are not enabled"}
            values = self.arrays[(forest, prop)]
            before, before_class = values[index]
            if mode == "null":
                value = None
                value_class = "UndefinedClass"
            elif mode == "node":
                value = self._decode(token)
                if value not in self.scene_nodes:
                    return {"ok": False, "error": "Node reference target was not found"}
                value_class = "line" if value == "Line001" else "Forest_Pro"
            else:
                return {"ok": False, "error": "Unsupported node reference mode"}
            values[index] = (value, value_class)
            return {"ok": True, "data": {
                "forest_name": forest, "property_name": prop, "index": index,
                "count": len(values), "reference_type": "node",
                "before_value": before, "after_value": value, "verified": True,
            }}
        if op == "FOREST_CONTROL_SET_ARRAY_SCALAR":
            forest = self._decode(parts[1]); prop = self._decode(parts[2]); index = int(parts[3])
            values = self.arrays[(forest, prop)]; before, cls = values[index]
            value = float(self._decode(parts[5])); values[index] = (value, cls)
            return {"ok": True, "data": {"before_value": before, "after_value": value, "verified": True}}
        if op == "FOREST_CONTROL_SET_ARRAY_POINT3":
            forest = self._decode(parts[1]); prop = self._decode(parts[2]); index = int(parts[3])
            values = self.arrays[(forest, prop)]; before, cls = values[index]
            value = [float(parts[4]), float(parts[5]), float(parts[6])]; values[index] = (value, cls)
            return {"ok": True, "data": {"before_value": list(before), "after_value": value, "verified": True}}
        raise AssertionError(command)


@pytest.fixture()
def bridge(monkeypatch):
    fake = FakeNodeReferenceBridge()
    monkeypatch.setattr(service_module, "ensure_current_bridge", lambda: {"ok": True})
    monkeypatch.setattr(service_module, "send_command", fake.send)
    return fake


def test_nullable_node_reference_write_readback_and_rollback(bridge):
    service = ForestPackControlService()
    before = service.get_array_element("FM_Forest_001", "arnodelist", 0)
    assert before["value"] is None
    assert before["reference_type"] == "node"
    result = service.set_array_element("FM_Forest_001", "arnodelist", 0, "Line001")
    assert result["verified"] is True
    assert result["reference_type"] == "node"
    assert result["after_value"] == "Line001"
    rollback = service.rollback()
    assert len(rollback) == 1
    assert rollback[0]["index"] == 0
    assert bridge.arrays[("FM_Forest_001", "arnodelist")][0][0] is None


def test_node_reference_target_and_property_guards(bridge):
    service = ForestPackControlService()
    with pytest.raises(ForestControlError, match="non-empty scene node name or None"):
        service.set_array_element("FM_Forest_001", "arnodelist", 0, "")
    with pytest.raises(ForestControlError, match="target was not found"):
        service.set_array_element("FM_Forest_001", "arnodelist", 0, "MissingNode")
    with pytest.raises(ForestControlError):
        service.set_array_element("FM_Forest_001", "cobjlist", 0, "Line001")
    assert service.rollback() == []


def test_existing_node_reference_can_be_cleared_and_restored(bridge):
    service = ForestPackControlService()
    assert service.get_array_element("FM_Forest_001", "arnodelist", 1)["value"] == "Line001"
    service.set_array_element("FM_Forest_001", "arnodelist", 1, None)
    assert bridge.arrays[("FM_Forest_001", "arnodelist")][1][0] is None
    service.rollback()
    assert bridge.arrays[("FM_Forest_001", "arnodelist")][1][0] == "Line001"


def test_mixed_array_scalar_point3_and_node_reference_journal(bridge):
    service = ForestPackControlService()
    service.set_array_element("FM_Forest_001", "ScaleList", 0, 101.0)
    service.set_array_element("FM_Forest_001", "coloridlist", 0, [149, 177, 27])
    service.set_array_element("FM_Forest_001", "arnodelist", 0, "Line001")
    rollback = service.rollback()
    assert len(rollback) == 3
    assert bridge.arrays[("FM_Forest_001", "ScaleList")][0][0] == 100.0
    assert bridge.arrays[("FM_Forest_001", "coloridlist")][0][0] == [148.0, 177.0, 27.0]
    assert bridge.arrays[("FM_Forest_001", "arnodelist")][0][0] is None


def test_stage65_bridge_contract_and_stable_startup_loader():
    root = Path(__file__).resolve().parents[1]
    bridge_text = (root / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    runtime_text = (root / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert "FOREST_CONTROL_SET_ARRAY_NODE_REF" in bridge_text
    assert "fn forestControlSetArrayNodeReferenceJson" in bridge_text
    assert "arnodelist" in bridge_text
    assert "stage6-8-cproxy-reference-write-20260816a" in bridge_text
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage6-8-cproxy-reference-write-20260816a"' in runtime_text
    assert "catch (throw" not in bridge_text
    loader_section = runtime_text.split("def _startup_loader_text", 1)[1].split("def install_startup_bridge_loader", 1)[0]
    assert "EXPECTED_BRIDGE_BUILD_ID" not in loader_section
    assert "ForestManager_Bridge.ms" not in loader_section
