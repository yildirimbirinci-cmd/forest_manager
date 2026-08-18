from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from .service import ForestControlError, SceneUnitContext


_DISPLAY_UNIT_ALIASES = {
    "meter": ("m", "one_meter_system_units"),
    "meters": ("m", "one_meter_system_units"),
    "metre": ("m", "one_meter_system_units"),
    "metres": ("m", "one_meter_system_units"),
    "m": ("m", "one_meter_system_units"),
    "centimeter": ("cm", "one_centimeter_system_units"),
    "centimeters": ("cm", "one_centimeter_system_units"),
    "centimetre": ("cm", "one_centimeter_system_units"),
    "centimetres": ("cm", "one_centimeter_system_units"),
    "cm": ("cm", "one_centimeter_system_units"),
    "millimeter": ("mm", "one_millimeter_system_units"),
    "millimeters": ("mm", "one_millimeter_system_units"),
    "millimetre": ("mm", "one_millimeter_system_units"),
    "millimetres": ("mm", "one_millimeter_system_units"),
    "mm": ("mm", "one_millimeter_system_units"),
}


@dataclass(frozen=True)
class DisplayDistanceContract:
    system_units_per_display_unit: float
    suffix: str


class UnitConversionGateway:
    """Central unit conversion policy for active-scene display/system units."""

    @staticmethod
    def _finite_number(value: Any, label: str) -> float:
        if isinstance(value, bool):
            raise ForestControlError(f"{label} must be a finite number.")
        try:
            resolved = float(value)
        except (TypeError, ValueError) as exc:
            raise ForestControlError(f"{label} must be a finite number.") from exc
        if not math.isfinite(resolved):
            raise ForestControlError(f"{label} must be a finite number.")
        return resolved

    @classmethod
    def display_contract(
        cls,
        units: SceneUnitContext | Mapping[str, Any] | None,
    ) -> DisplayDistanceContract:
        if units is None:
            return DisplayDistanceContract(1.0, "units")

        if isinstance(units, SceneUnitContext):
            display_unit = str(units.display_unit or "").strip()
            values = {
                "one_meter_system_units": units.one_meter_system_units,
                "one_centimeter_system_units": units.one_centimeter_system_units,
                "one_millimeter_system_units": units.one_millimeter_system_units,
            }
        else:
            display_unit = str(units.get("display_unit") or "").strip()
            values = {
                "one_meter_system_units": units.get("one_meter_system_units"),
                "one_centimeter_system_units": units.get("one_centimeter_system_units"),
                "one_millimeter_system_units": units.get("one_millimeter_system_units"),
            }

        alias = _DISPLAY_UNIT_ALIASES.get(display_unit.lower())
        if alias is None:
            return DisplayDistanceContract(1.0, display_unit or "units")

        suffix, factor_key = alias
        factor = cls._finite_number(values.get(factor_key), factor_key)
        if factor <= 0.0:
            raise ForestControlError(f"Active scene display-unit conversion is invalid: {display_unit or suffix}")
        return DisplayDistanceContract(factor, suffix)

    @classmethod
    def system_to_display(
        cls,
        value: Any,
        units: SceneUnitContext | Mapping[str, Any] | None,
    ) -> tuple[float, str]:
        resolved = cls._finite_number(value, "System-unit value")
        contract = cls.display_contract(units)
        return resolved / contract.system_units_per_display_unit, contract.suffix

    @classmethod
    def display_to_system(
        cls,
        value: Any,
        units: SceneUnitContext | Mapping[str, Any] | None,
    ) -> float:
        resolved = cls._finite_number(value, "Display distance")
        contract = cls.display_contract(units)
        return resolved * contract.system_units_per_display_unit
