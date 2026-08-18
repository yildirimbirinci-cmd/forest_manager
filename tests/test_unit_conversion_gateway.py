from __future__ import annotations

from dataclasses import replace

import pytest

from forest_manager.forest_control.service import ForestControlError, SceneUnitContext
from forest_manager.forest_control.unit_conversion import UnitConversionGateway


def _units(display_unit: str = "Meters") -> SceneUnitContext:
    return SceneUnitContext(
        display_type="#Metric",
        display_unit=display_unit,
        system_type="#Centimeters",
        system_scale=1.0,
        one_meter_system_units=100.0,
        one_centimeter_system_units=1.0,
        one_millimeter_system_units=0.1,
        sample_one_meter_display="1.0m",
    )


def test_gateway_converts_active_meter_display_units():
    units = _units("Meters")
    assert UnitConversionGateway.display_to_system(75.0, units) == 7500.0
    value, suffix = UnitConversionGateway.system_to_display(7500.0, units)
    assert value == 75.0
    assert suffix == "m"


def test_gateway_supports_centimeters_and_millimeters():
    cm = _units("Centimeters")
    mm = _units("Millimeters")

    assert UnitConversionGateway.display_to_system(25.0, cm) == 25.0
    assert UnitConversionGateway.system_to_display(25.0, cm) == (25.0, "cm")

    assert UnitConversionGateway.display_to_system(250.0, mm) == 25.0
    assert UnitConversionGateway.system_to_display(25.0, mm) == (250.0, "mm")


def test_gateway_accepts_ui_payload_mapping():
    units = _units("Meters")
    payload = {
        "display_unit": units.display_unit,
        "one_meter_system_units": units.one_meter_system_units,
        "one_centimeter_system_units": units.one_centimeter_system_units,
        "one_millimeter_system_units": units.one_millimeter_system_units,
    }
    assert UnitConversionGateway.display_to_system(10.0, payload) == 1000.0
    assert UnitConversionGateway.system_to_display(1000.0, payload) == (10.0, "m")


def test_gateway_rejects_invalid_active_conversion_factor():
    units = replace(_units("Meters"), one_meter_system_units=0.0)
    with pytest.raises(ForestControlError, match="conversion is invalid"):
        UnitConversionGateway.display_to_system(1.0, units)
