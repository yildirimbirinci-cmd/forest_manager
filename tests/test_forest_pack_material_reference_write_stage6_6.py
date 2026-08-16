from __future__ import annotations

import base64
from pathlib import Path

import pytest

import forest_manager.forest_control.service as service_module
from forest_manager.forest_control.service import ForestControlError, ForestPackControlService


BUILD = "stage6-6-material-reference-write-20260816a"


class FakeMaterialReferenceBridge:
    def __init__(self):
        self.arrays = {
            ("FM_Forest_001", "matlist"): [
                ("Material_A", "Multimaterial"),
                ("Material_B", "Multimaterial"),
            ],
            ("FM_Forest_001", "arnodelist"): [(None, "UndefinedClass"), ("Line001", "line")],
            ("FM_Forest_001", "cobjlist"): [("Lavandula", "CProxy")],
            ("FM_Forest_001", "ScaleList"): [(100.0, "Float")],
            ("FM_Forest_001", "coloridlist"): [([148.0, 177.0, 27.0], "Point3")],
        }
        self.scene_materials = {"Material_A", "Material_B"}
        self.scene_nodes = {"Line001"}

    @staticmethod
    def _decode(token: str) -> str:
        return base64.b64decode(token.encode("ascii")).decode("utf-8")

    def send(self, command: str):
        parts = command.split("|")
        op = parts[0]
        if op == "FOREST_CONTROL_GET_ARRAY_ELEMENT":
            forest = self._decode(parts[1]); prop = self._decode(parts[2]); index = int(parts[3])
            values = self.arrays[(forest, prop)]; value, value_class = values[index]
            reference_type = "material" if prop == "matlist" else ("node" if prop == "arnodelist" else "")
            scalar_type = "float" if value_class == "Float" else ""
            vector_type = "point3" if value_class == "Point3" else ""
            if prop == "cobjlist":
                return {"ok": False, "error": "not writable by a verified endpoint: CProxy"}
            return {"ok": True, "data": {
                "forest_name": forest, "property_name": prop, "index": index, "count": len(values),
                "value_class": value_class, "scalar_type": scalar_type, "vector_type": vector_type,
                "reference_type": reference_type, "value": list(value) if value_class == "Point3" else value,
                "verified": True,
            }}
        if op == "FOREST_CONTROL_SET_ARRAY_MATERIAL_REF":
            forest = self._decode(parts[1]); prop = self._decode(parts[2]); index = int(parts[3])
            if prop != "matlist":
                return {"ok": False, "error": "Material reference array writes are not enabled"}
            values = self.arrays[(forest, prop)]; before, _ = values[index]
            mode = parts[4]
            if mode == "null":
                value = None; cls = "UndefinedClass"
            elif mode == "material":
                value = self._decode(parts[5])
                if value not in self.scene_materials:
                    return {"ok": False, "error": "Material reference target was not found"}
                cls = "Multimaterial"
            else:
                return {"ok": False, "error": "Unsupported material reference mode"}
            values[index] = (value, cls)
            return {"ok": True, "data": {
                "forest_name": forest, "property_name": prop, "index": index, "count": len(values),
                "reference_type": "material", "before_value": before, "after_value": value, "verified": True,
            }}
        if op == "FOREST_CONTROL_SET_ARRAY_NODE_REF":
            forest = self._decode(parts[1]); prop = self._decode(parts[2]); index = int(parts[3]); values = self.arrays[(forest, prop)]
            before, _ = values[index]; mode = parts[4]
            value = None if mode == "null" else self._decode(parts[5])
            if value is not None and value not in self.scene_nodes:
                return {"ok": False, "error": "Node reference target was not found"}
            values[index] = (value, "UndefinedClass" if value is None else "line")
            return {"ok": True, "data": {"before_value": before, "after_value": value, "verified": True}}
        if op == "FOREST_CONTROL_SET_ARRAY_SCALAR":
            forest = self._decode(parts[1]); prop = self._decode(parts[2]); index = int(parts[3]); values = self.arrays[(forest, prop)]
            before, cls = values[index]; value = float(self._decode(parts[5])); values[index] = (value, cls)
            return {"ok": True, "data": {"before_value": before, "after_value": value, "verified": True}}
        if op == "FOREST_CONTROL_SET_ARRAY_POINT3":
            forest = self._decode(parts[1]); prop = self._decode(parts[2]); index = int(parts[3]); values = self.arrays[(forest, prop)]
            before, cls = values[index]; value = [float(parts[4]), float(parts[5]), float(parts[6])]; values[index] = (value, cls)
            return {"ok": True, "data": {"before_value": list(before), "after_value": value, "verified": True}}
        raise AssertionError(command)


@pytest.fixture()
def bridge(monkeypatch):
    fake = FakeMaterialReferenceBridge()
    monkeypatch.setattr(service_module, "ensure_current_bridge", lambda: {"ok": True})
    monkeypatch.setattr(service_module, "send_command", fake.send)
    return fake


def test_material_reference_write_readback_and_rollback(bridge):
    service = ForestPackControlService()
    before = service.get_array_element("FM_Forest_001", "matlist", 0)
    assert before["reference_type"] == "material"
    assert before["value"] == "Material_A"
    result = service.set_array_element("FM_Forest_001", "matlist", 0, "Material_B")
    assert result["verified"] is True
    assert result["reference_type"] == "material"
    assert bridge.arrays[("FM_Forest_001", "matlist")][0][0] == "Material_B"
    rollback = service.rollback()
    assert len(rollback) == 1
    assert rollback[0]["index"] == 0
    assert bridge.arrays[("FM_Forest_001", "matlist")][0][0] == "Material_A"


def test_material_reference_guards(bridge):
    service = ForestPackControlService()
    with pytest.raises(ForestControlError, match="non-empty scene material name or None"):
        service.set_array_element("FM_Forest_001", "matlist", 0, "")
    with pytest.raises(ForestControlError, match="target was not found"):
        service.set_array_element("FM_Forest_001", "matlist", 0, "MissingMaterial")
    with pytest.raises(ForestControlError):
        service.set_array_element("FM_Forest_001", "cobjlist", 0, "Material_B")
    assert service.rollback() == []


def test_nullable_material_reference_and_restore(bridge):
    service = ForestPackControlService()
    service.set_array_element("FM_Forest_001", "matlist", 0, None)
    assert bridge.arrays[("FM_Forest_001", "matlist")][0][0] is None
    service.rollback()
    assert bridge.arrays[("FM_Forest_001", "matlist")][0][0] == "Material_A"


def test_mixed_scalar_point3_node_and_material_reference_journal(bridge):
    service = ForestPackControlService()
    service.set_array_element("FM_Forest_001", "ScaleList", 0, 101.0)
    service.set_array_element("FM_Forest_001", "coloridlist", 0, [149, 177, 27])
    service.set_array_element("FM_Forest_001", "arnodelist", 0, "Line001")
    service.set_array_element("FM_Forest_001", "matlist", 0, "Material_B")
    rollback = service.rollback()
    assert len(rollback) == 4
    assert bridge.arrays[("FM_Forest_001", "ScaleList")][0][0] == 100.0
    assert bridge.arrays[("FM_Forest_001", "coloridlist")][0][0] == [148.0, 177.0, 27.0]
    assert bridge.arrays[("FM_Forest_001", "arnodelist")][0][0] is None
    assert bridge.arrays[("FM_Forest_001", "matlist")][0][0] == "Material_A"


def test_stage66_bridge_contract_and_stable_startup_loader():
    root = Path(__file__).resolve().parents[1]
    bridge_text = (root / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    runtime_text = (root / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert "FOREST_CONTROL_SET_ARRAY_MATERIAL_REF" in bridge_text
    assert "fn forestControlSetArrayMaterialReferenceJson" in bridge_text
    assert "matlist" in bridge_text
    assert BUILD in bridge_text
    assert f'EXPECTED_BRIDGE_BUILD_ID = "{BUILD}"' in runtime_text
    assert "catch (throw" not in bridge_text
    loader_section = runtime_text.split("def _startup_loader_text", 1)[1].split("def install_startup_bridge_loader", 1)[0]
    assert "EXPECTED_BRIDGE_BUILD_ID" not in loader_section
    assert "ForestManager_Bridge.ms" not in loader_section
