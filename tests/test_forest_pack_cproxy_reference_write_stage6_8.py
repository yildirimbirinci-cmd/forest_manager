from __future__ import annotations

import base64
from pathlib import Path

import pytest

import forest_manager.forest_control.service as service_module
from forest_manager.forest_control.service import ForestControlError, ForestPackControlService

BUILD = "stage8-world-map-projection-20260818q"


class FakeCProxyReferenceBridge:
    def __init__(self):
        self.arrays = {
            ("FM_Forest_001", "cobjlist"): ["LavenderProxy", "RushProxy", "BerberisProxy"],
            ("FM_Forest_001", "arnodelist"): [None, "Line001"],
        }
        self.classes = {
            "LavenderProxy": "CProxy",
            "RushProxy": "CProxy",
            "BerberisProxy": "CProxy",
            "Line001": "line",
        }

    @staticmethod
    def _decode(token: str) -> str:
        return base64.b64decode(token.encode("ascii")).decode("utf-8")

    def send(self, command: str):
        parts = command.split("|")
        op = parts[0]
        if op == "FOREST_CONTROL_GET_ARRAY_ELEMENT":
            forest = self._decode(parts[1]); prop = self._decode(parts[2]); index = int(parts[3])
            values = self.arrays[(forest, prop)]
            value = values[index]
            if prop == "cobjlist":
                ref_type = "cproxy"
                value_class = "UndefinedClass" if value is None else self.classes[value]
            else:
                ref_type = "node"
                value_class = "UndefinedClass" if value is None else self.classes[value]
            return {"ok": True, "data": {
                "forest_name": forest, "property_name": prop, "index": index,
                "count": len(values), "value_class": value_class,
                "scalar_type": "", "vector_type": "", "reference_type": ref_type,
                "value": value, "verified": True,
            }}
        if op == "FOREST_CONTROL_SET_ARRAY_CPROXY_REF":
            forest = self._decode(parts[1]); prop = self._decode(parts[2]); index = int(parts[3])
            mode = parts[4]
            if prop != "cobjlist":
                return {"ok": False, "error": "CProxy reference array writes are not enabled"}
            values = self.arrays[(forest, prop)]
            before = values[index]
            if mode == "null":
                value = None
            elif mode == "cproxy":
                value = self._decode(parts[5])
                if self.classes.get(value) != "CProxy":
                    return {"ok": False, "error": "CProxy reference target is not CProxy"}
            else:
                return {"ok": False, "error": "Unsupported CProxy reference mode"}
            values[index] = value
            return {"ok": True, "data": {
                "forest_name": forest, "property_name": prop, "index": index,
                "count": len(values), "reference_type": "cproxy",
                "before_value": before, "after_value": value, "verified": True,
            }}
        raise AssertionError(command)


@pytest.fixture()
def bridge(monkeypatch):
    fake = FakeCProxyReferenceBridge()
    monkeypatch.setattr(service_module, "ensure_current_bridge", lambda: {"ok": True})
    monkeypatch.setattr(service_module, "send_command", fake.send)
    return fake


def test_cproxy_reference_write_readback_and_rollback(bridge):
    service = ForestPackControlService()
    before = service.get_array_element("FM_Forest_001", "cobjlist", 0)
    target = service.get_array_element("FM_Forest_001", "cobjlist", 1)["value"]
    result = service.set_array_element("FM_Forest_001", "cobjlist", 0, target)
    assert result["verified"] is True
    assert result["reference_type"] == "cproxy"
    assert bridge.arrays[("FM_Forest_001", "cobjlist")][0] == target
    steps = service.rollback()
    assert len(steps) == 1
    assert steps[0]["index"] == 0
    assert bridge.arrays[("FM_Forest_001", "cobjlist")][0] == before["value"]


def test_cproxy_reference_nullable_and_allowlist_guards(bridge):
    service = ForestPackControlService()
    original = bridge.arrays[("FM_Forest_001", "cobjlist")][0]
    service.set_array_element("FM_Forest_001", "cobjlist", 0, None)
    assert bridge.arrays[("FM_Forest_001", "cobjlist")][0] is None
    service.rollback()
    assert bridge.arrays[("FM_Forest_001", "cobjlist")][0] == original
    with pytest.raises(ForestControlError, match="non-empty scene node name"):
        service.set_array_element("FM_Forest_001", "cobjlist", 0, "")
    with pytest.raises(ForestControlError):
        service._send_array_cproxy_reference("FM_Forest_001", "arnodelist", 0, "LavenderProxy", preflight=False)


def test_cproxy_reference_target_must_be_cproxy(bridge):
    service = ForestPackControlService()
    with pytest.raises(ForestControlError, match="not CProxy"):
        service.set_array_element("FM_Forest_001", "cobjlist", 0, "Line001")


def test_stage68_bridge_contract_and_stable_loader():
    root = Path(__file__).resolve().parents[1]
    bridge_text = (root / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    runtime_text = (root / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert "FOREST_CONTROL_SET_ARRAY_CPROXY_REF" in bridge_text
    assert "fn forestControlSetArrayCProxyReferenceJson" in bridge_text
    assert 'propertyName) != "cobjlist"' in bridge_text
    assert 'safeClassName newValue != "CProxy"' in bridge_text
    assert 'referenceType = "cproxy"' in bridge_text
    assert BUILD in bridge_text
    assert f'EXPECTED_BRIDGE_BUILD_ID = "{BUILD}"' in runtime_text
    assert "catch (throw" not in bridge_text
    loader_section = runtime_text.split("def _startup_loader_text", 1)[1].split("def install_startup_bridge_loader", 1)[0]
    assert "EXPECTED_BRIDGE_BUILD_ID" not in loader_section
    assert "ForestManager_Bridge.ms" not in loader_section
