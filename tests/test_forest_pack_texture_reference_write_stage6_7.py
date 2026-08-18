from __future__ import annotations

import base64
from pathlib import Path

import pytest

import forest_manager.forest_control.service as service_module
from forest_manager.forest_control.service import ForestControlError, ForestPackControlService

BUILD = "stage8-world-map-projection-20260818q"


class FakeTextureReferenceBridge:
    def __init__(self):
        self.textures = {
            "FM_Forest_001": "anim:101",
            "FM_Layer_02_mid_accent": "anim:202",
        }
        self.filenames = {
            "anim:101": "",
            "anim:202": r"C:\\masks\\accent.png",
        }
        self.available = set(self.textures.values())

    @staticmethod
    def _decode(token: str) -> str:
        return base64.b64decode(token.encode("ascii")).decode("utf-8")

    def send(self, command: str):
        parts = command.split("|")
        op = parts[0]
        if op == "FOREST_CONTROL_GET_TEXTURE_REF":
            forest = self._decode(parts[1]); prop = self._decode(parts[2])
            if prop != "distmap":
                return {"ok": False, "error": "Texture reference writes are not enabled"}
            value = self.textures.get(forest)
            return {"ok": True, "data": {
                "forest_name": forest, "property_name": prop,
                "value_class": "UndefinedClass" if value is None else "Bitmaptexture",
                "reference_type": "texture", "value": value,
                "filename": "" if value is None else self.filenames.get(value, ""),
                "verified": True,
            }}
        if op == "FOREST_CONTROL_SET_TEXTURE_REF":
            forest = self._decode(parts[1]); prop = self._decode(parts[2]); mode = parts[3]
            if prop != "distmap":
                return {"ok": False, "error": "Texture reference writes are not enabled"}
            before = self.textures.get(forest)
            if mode == "null":
                value = None
            elif mode == "anim":
                value = self._decode(parts[4])
                if value not in self.available:
                    return {"ok": False, "error": "Texture reference target was not found"}
            elif mode == "bitmap":
                filename = self._decode(parts[4])
                matches = [tok for tok, path in self.filenames.items() if path == filename]
                if not matches:
                    return {"ok": False, "error": "Texture reference target was not found"}
                value = matches[0]
            else:
                return {"ok": False, "error": "Unsupported texture reference mode"}
            self.textures[forest] = value
            return {"ok": True, "data": {
                "forest_name": forest, "property_name": prop, "reference_type": "texture",
                "before_value": before, "after_value": value, "verified": True,
            }}
        raise AssertionError(command)


@pytest.fixture()
def bridge(monkeypatch):
    fake = FakeTextureReferenceBridge()
    monkeypatch.setattr(service_module, "ensure_current_bridge", lambda: {"ok": True})
    monkeypatch.setattr(service_module, "send_command", fake.send)
    return fake


def test_texture_reference_animhandle_write_readback_and_rollback(bridge):
    service = ForestPackControlService()
    before = service.get_texture_reference("FM_Forest_001")
    assert before["reference_type"] == "texture"
    assert before["value"] == "anim:101"
    assert before["filename"] == ""
    target = bridge.textures["FM_Layer_02_mid_accent"]
    result = service.set_property("FM_Forest_001", "distmap", target)
    assert result["verified"] is True
    assert bridge.textures["FM_Forest_001"] == target
    rollback = service.rollback()
    assert len(rollback) == 1
    assert bridge.textures["FM_Forest_001"] == before["value"]


def test_texture_reference_nullable_and_guards(bridge):
    service = ForestPackControlService()
    original = bridge.textures["FM_Forest_001"]
    service.set_property("FM_Forest_001", "distmap", None)
    assert bridge.textures["FM_Forest_001"] is None
    service.rollback()
    assert bridge.textures["FM_Forest_001"] == original
    with pytest.raises(ForestControlError, match="non-empty AnimHandle or bitmap filename token"):
        service.set_property("FM_Forest_001", "distmap", "")
    with pytest.raises(ForestControlError, match="Invalid texture AnimHandle token"):
        service.set_property("FM_Forest_001", "distmap", "anim:0")
    with pytest.raises(ForestControlError, match="target was not found"):
        service.set_property("FM_Forest_001", "distmap", "anim:999")
    with pytest.raises(ForestControlError, match="not enabled"):
        service.get_texture_reference("FM_Forest_001", "geomtex")


def test_texture_reference_write_from_undefined_slot_and_rollback(bridge):
    service = ForestPackControlService()
    bridge.textures["FM_Forest_001"] = None
    source = bridge.textures["FM_Layer_02_mid_accent"]
    result = service.set_property("FM_Forest_001", "distmap", source)
    assert result["verified"] is True
    assert bridge.textures["FM_Forest_001"] == source
    rollback = service.rollback()
    assert len(rollback) == 1
    assert bridge.textures["FM_Forest_001"] is None


def test_filename_fallback_remains_supported(bridge):
    service = ForestPackControlService()
    result = service.set_property("FM_Forest_001", "distmap", r"C:\\masks\\accent.png")
    assert result["verified"] is True
    assert bridge.textures["FM_Forest_001"] == "anim:202"


def test_stage67_bridge_contract_and_stable_startup_loader():
    root = Path(__file__).resolve().parents[1]
    bridge_text = (root / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    runtime_text = (root / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert "FOREST_CONTROL_GET_TEXTURE_REF" in bridge_text
    assert "FOREST_CONTROL_SET_TEXTURE_REF" in bridge_text
    assert "fn forestControlSetTextureReferenceJson" in bridge_text
    assert "GetHandleByAnim" in bridge_text
    assert "GetAnimByHandle" in bridge_text
    assert '"anim:"' in bridge_text
    assert "distmap" in bridge_text
    set_block = bridge_text.split('if matchPattern command pattern:"FOREST_CONTROL_SET_TEXTURE_REF|*"', 1)[1].split('if matchPattern command pattern:"FOREST_CONTROL_GET_TEXTURE_REF|*"', 1)[0]
    get_block = bridge_text.split('if matchPattern command pattern:"FOREST_CONTROL_GET_TEXTURE_REF|*"', 1)[1].split('if matchPattern command pattern:"FOREST_CONTROL_SET_ARRAY_MATERIAL_REF|*"', 1)[0]
    assert 'filterString cleanCommand "|"' in set_block
    assert 'filterString cleanCommand "|"' in get_block
    assert 'filterString command "|"' not in set_block
    assert 'filterString command "|"' not in get_block
    assert BUILD in bridge_text
    assert f'EXPECTED_BRIDGE_BUILD_ID = "{BUILD}"' in runtime_text
    assert "catch (throw" not in bridge_text
    loader_section = runtime_text.split("def _startup_loader_text", 1)[1].split("def install_startup_bridge_loader", 1)[0]
    assert "EXPECTED_BRIDGE_BUILD_ID" not in loader_section
    assert "ForestManager_Bridge.ms" not in loader_section


def test_texture_animhandle_integerptr_suffix_is_normalized(bridge):
    service = ForestPackControlService()
    bridge.textures["FM_Forest_001"] = None
    result = service.set_property("FM_Forest_001", "distmap", "anim:202P")
    assert result["verified"] is True
    assert bridge.textures["FM_Forest_001"] == "anim:202"

