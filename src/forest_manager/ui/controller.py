from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from forest_manager.forest_control.service import ForestControlError, ForestPackControlService


@dataclass(frozen=True)
class PropertyRow:
    name: str
    value_class: str
    write_mode: str
    readable: bool
    value: Any
    array_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ForestUIState:
    forest_names: tuple[str, ...] = ()
    selected_forest: str | None = None
    properties: tuple[PropertyRow, ...] = ()
    scene_units: dict[str, Any] | None = None
    bridge_online: bool = False
    status: str = "Not connected"
    error: str | None = None


class ForestManagerUIController:
    """Read-oriented Stage 7.1 application controller over the Stage 6 production backend."""

    def __init__(self, service: ForestPackControlService | None = None) -> None:
        self.service = service or ForestPackControlService()
        self._state = ForestUIState()

    @property
    def state(self) -> ForestUIState:
        return self._state

    @staticmethod
    def _unit_payload(units: Any) -> dict[str, Any]:
        return {
            "display_type": units.display_type,
            "display_unit": units.display_unit,
            "system_type": units.system_type,
            "system_scale": units.system_scale,
            "one_meter_system_units": units.one_meter_system_units,
            "one_centimeter_system_units": units.one_centimeter_system_units,
            "one_millimeter_system_units": units.one_millimeter_system_units,
            "sample_one_meter_display": units.sample_one_meter_display,
            "custom_name": units.custom_name,
            "custom_value": units.custom_value,
            "custom_unit": units.custom_unit,
        }

    @staticmethod
    def _property_rows(inventory: dict[str, Any]) -> tuple[PropertyRow, ...]:
        rows: list[PropertyRow] = []
        for item in inventory.get("properties") or []:
            if not isinstance(item, dict):
                continue
            rows.append(
                PropertyRow(
                    name=str(item.get("name") or ""),
                    value_class=str(item.get("value_class") or ""),
                    write_mode=str(item.get("write_mode") or "read_only"),
                    readable=bool(item.get("readable")),
                    value=item.get("value"),
                    array_metadata=item.get("array_metadata") if isinstance(item.get("array_metadata"), dict) else None,
                )
            )
        return tuple(rows)

    def _load_forest(self, forest_name: str, *, preflight: bool) -> ForestUIState:
        inventory = self.service.inventory(forest_name, preflight=preflight)
        properties = self._property_rows(inventory)
        units = self.service.scene_units(preflight=False)
        forests = self.service.list_forests(preflight=False)
        if forest_name not in forests:
            raise ForestControlError(f"Forest target became stale while loading UI state: {forest_name}")
        self._state = ForestUIState(
            forest_names=tuple(forests),
            selected_forest=forest_name,
            properties=properties,
            scene_units=self._unit_payload(units),
            bridge_online=True,
            status=f"Loaded {forest_name}: {len(properties)} properties",
            error=None,
        )
        return self._state

    def refresh_scene(self, *, prefer_max_selection: bool = True) -> ForestUIState:
        try:
            forests = self.service.list_forests(preflight=True)
            units = self.service.scene_units(preflight=False)
            if not forests:
                self._state = ForestUIState(
                    forest_names=(),
                    selected_forest=None,
                    properties=(),
                    scene_units=self._unit_payload(units),
                    bridge_online=True,
                    status="Connected: no Forest objects found",
                    error=None,
                )
                return self._state

            selected: str | None = None
            if prefer_max_selection:
                try:
                    selected = self.service.selected_forest_name(preflight=False)
                except ForestControlError:
                    selected = None
            if selected not in forests:
                if self._state.selected_forest in forests:
                    selected = self._state.selected_forest
                else:
                    selected = forests[0]
            return self._load_forest(str(selected), preflight=False)
        except Exception as exc:
            self._state = replace(
                self._state,
                bridge_online=False,
                status="Forest Manager backend unavailable",
                error=f"{type(exc).__name__}: {exc}",
            )
            return self._state

    def select_forest(self, forest_name: str) -> ForestUIState:
        try:
            candidate = forest_name.strip() if isinstance(forest_name, str) else ""
            if not candidate:
                raise ForestControlError("Forest selection must be a non-empty name.")
            forests = self.service.list_forests(preflight=True)
            if candidate not in forests:
                raise ForestControlError(f"Selected Forest is stale or missing: {candidate}")
            return self._load_forest(candidate, preflight=False)
        except Exception as exc:
            self._state = replace(
                self._state,
                status="Forest selection failed",
                error=f"{type(exc).__name__}: {exc}",
            )
            return self._state

    def select_max_selection(self) -> ForestUIState:
        try:
            selected = self.service.selected_forest_name(preflight=True)
            return self._load_forest(selected, preflight=False)
        except Exception as exc:
            self._state = replace(
                self._state,
                status="3ds Max selection is not a Forest",
                error=f"{type(exc).__name__}: {exc}",
            )
            return self._state
