from __future__ import annotations

import base64

import pytest

import forest_manager.forest_control.service as service_module
from forest_manager.forest_control.service import ForestControlError, ForestPackControlService


class FakeBridge:
    def __init__(self):
        self.values = {
            ("FM_Forest_001", "seed"): (123456, "Integer", "scalar"),
            ("FM_Forest_001", "mirror"): (False, "BooleanClass", "scalar"),
            ("FM_Forest_001", "iconSize"): (100.0, "Float", "scalar"),
            ("FM_Forest_001", "label"): ("alpha", "String", "scalar"),
            ("FM_Forest_001", "cobjlist"): (None, "ArrayParameter", "read_only"),
            ("FM_Forest_001", "falloff") : (None, "CurveControl", "read_only"),
            ("FM_Forest_001", "fastopac"): (False, "BooleanClass", "scalar"),
        }

    @staticmethod
    def _decode(token: str) -> str:
        return base64.b64decode(token.encode("ascii")).decode("utf-8")

    def send(self, command: str):
        parts = command.split("|")
        if parts[0] == "FOREST_CONTROL_DISCOVER":
            properties = []
            scalar_count = 0
            read_only_count = 0
            for (forest, prop), (value, value_class, write_mode) in self.values.items():
                if forest != "FM_Forest_001":
                    continue
                if write_mode == "scalar":
                    scalar_count += 1
                else:
                    read_only_count += 1
                properties.append({
                    "name": prop,
                    "value_class": value_class,
                    "write_mode": write_mode,
                    "readable": True,
                    "value": value,
                })
            return {
                "ok": True,
                "data": {
                    "read_only": True,
                    "forest_count": 1,
                    "forests": [{
                        "forest_name": "FM_Forest_001",
                        "property_count": len(properties),
                        "write_mode_counts": {
                            "read_only": read_only_count,
                            "scalar": scalar_count,
                            "color": 0,
                        },
                        "properties": properties,
                        "arrays": [],
                    }],
                    "verified": True,
                },
            }
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
        if parts[0] == "FOREST_CONTROL_SET_SCALAR":
            forest = self._decode(parts[1])
            prop = self._decode(parts[2])
            scalar_type = parts[3]
            text = self._decode(parts[4])
            before, value_class, write_mode = self.values[(forest, prop)]
            assert write_mode == "scalar"
            if scalar_type == "bool":
                value = text == "true"
            elif scalar_type == "int":
                value = int(text)
            elif scalar_type == "float":
                value = float(text)
            elif scalar_type == "string":
                value = text
            else:
                raise AssertionError(scalar_type)
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
    fake = FakeBridge()
    monkeypatch.setattr(service_module, "ensure_current_bridge", lambda: {"ok": True})
    monkeypatch.setattr(service_module, "send_command", fake.send)
    return fake


def test_scalar_families_write_verify_and_rollback(bridge):
    service = ForestPackControlService()
    original = {key: value[0] for key, value in bridge.values.items()}
    assert service.set_property("FM_Forest_001", "seed", 123457)["verified"] is True
    assert service.set_property("FM_Forest_001", "mirror", True)["verified"] is True
    assert service.set_property("FM_Forest_001", "iconSize", 101.5)["verified"] is True
    assert service.set_property("FM_Forest_001", "label", "beta")["verified"] is True
    results = service.rollback()
    assert len(results) == 4
    assert {key: value[0] for key, value in bridge.values.items()} == original
    assert service.rollback() == []


def test_read_only_array_and_curve_properties_are_rejected_before_write(bridge):
    service = ForestPackControlService()
    with pytest.raises(ForestControlError, match="not writable by a verified endpoint"):
        service.set_property("FM_Forest_001", "cobjlist", 1)
    with pytest.raises(ForestControlError, match="not writable by a verified endpoint"):
        service.set_property("FM_Forest_001", "falloff", 1.0)
    with pytest.raises(ForestControlError, match="explicitly read-only"):
        service.set_property("FM_Forest_001", "fastopac", True)


def test_type_mismatch_is_rejected_without_scene_write(bridge):
    service = ForestPackControlService()
    before = bridge.values[("FM_Forest_001", "seed")]
    with pytest.raises(ForestControlError, match="Integer property requires int"):
        service.set_property("FM_Forest_001", "seed", True)
    assert bridge.values[("FM_Forest_001", "seed")] == before


def test_bridge_contract_exposes_stage61_commands_and_build_identity():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    bridge_text = (root / "maxscripts" / "ForestManager_Bridge.ms").read_text(encoding="utf-8")
    runtime_text = (root / "src" / "forest_manager" / "max_bridge" / "runtime_bridge.py").read_text(encoding="utf-8")
    assert "FOREST_CONTROL_GET_PROPERTY" in bridge_text
    assert "FOREST_CONTROL_SET_SCALAR" in bridge_text
    assert "forestControlExplicitReadOnly" in bridge_text
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.54"' in runtime_text
    build_line = next(line for line in runtime_text.splitlines() if line.startswith("EXPECTED_BRIDGE_BUILD_ID = "))
    build_id = build_line.split('"', 2)[1]
    assert build_id == "stage8-13-atomic-source-area-contract-20260816a"
    assert build_id in bridge_text


def test_existing_semantic_transaction_stack_uses_new_write_endpoint(bridge):
    from forest_manager.forest_control.semantic_api import SemanticForestControlAPI
    from forest_manager.forest_control.semantic_transaction import SemanticScalarChange, SemanticTransactionManager

    service = ForestPackControlService()
    api = SemanticForestControlAPI(service)
    manager = SemanticTransactionManager(service, api)
    before = bridge.values[("FM_Forest_001", "seed")][0]
    descriptor = api.describe("distribution", "extended_distribution_controls", "seed")
    assert descriptor.route == "scalar_direct"
    assert descriptor.writable is True
    result = manager.apply_and_rollback(
        "FM_Forest_001",
        (SemanticScalarChange("distribution", "extended_distribution_controls", "seed", before + 1),),
    )
    assert result.operation_count == 1
    assert result.blocked_operation_count == 0
    assert result.rollback_step_count == 1
    assert result.runtime_write_endpoint is True
    assert result.runtime_rollback_endpoint is True
    assert result.write_verified is True
    assert result.rollback_verified is True
    assert bridge.values[("FM_Forest_001", "seed")][0] == before
