from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from forest_manager.forest_control.schema import semantic_domains
from forest_manager.forest_control.service import ForestControlError, ForestPackControlService
from forest_manager.forest_control.semantic_transaction import (
    UnifiedControlOperation,
    UnifiedControlTransactionManager,
)

from .semantic_controls import (
    ArtistControlState,
    artist_control_specs,
    calibration_probe_keys,
    default_artist_values,
)
from .semantic_calibration import (
    CLUSTER_CHARACTER_CANDIDATES,
    NATURALNESS_CANDIDATES,
    SemanticCalibrationPlanner,
)


DOMAIN_LABELS = {
    "geometry": "Geometry",
    "areas": "Areas",
    "distribution": "Distribution",
    "transform": "Transform",
    "surface": "Surface / Camera",
    "camera": "Surface / Camera",
    "material": "Material / Animation",
    "animation": "Material / Animation",
    "display": "Display / Render / Effects",
    "collision": "Display / Render / Effects",
    "effects": "Display / Render / Effects",
}


@dataclass(frozen=True)
class PropertyRow:
    name: str
    value_class: str
    write_mode: str
    readable: bool
    value: Any
    array_metadata: dict[str, Any] | None = None
    domain: str = "Other"
    control: str = ""
    writable: bool = False
    editor_kind: str = "read_only"


@dataclass(frozen=True)
class PendingEdit:
    property_name: str
    original_value: Any
    value: Any
    editor_kind: str


@dataclass(frozen=True)
class ForestUIState:
    forest_names: tuple[str, ...] = ()
    selected_forest: str | None = None
    properties: tuple[PropertyRow, ...] = ()
    scene_units: dict[str, Any] | None = None
    pending_edits: tuple[PendingEdit, ...] = ()
    artist_controls: tuple[ArtistControlState, ...] = ()
    bridge_online: bool = False
    status: str = "Not connected"
    error: str | None = None


class ForestManagerUIController:
    """Stage 7 UI controller over the verified Stage 6 production backend."""

    def __init__(
        self,
        service: ForestPackControlService | None = None,
        transaction_manager: UnifiedControlTransactionManager | None = None,
    ) -> None:
        self.service = service or ForestPackControlService()
        self.transaction_manager = transaction_manager or UnifiedControlTransactionManager(self.service)
        self._state = ForestUIState()
        self._pending: dict[str, PendingEdit] = {}
        self._semantic_map = self._build_semantic_map()
        self._artist_values = default_artist_values()

    @property
    def state(self) -> ForestUIState:
        return self._state

    @staticmethod
    def _build_semantic_map() -> dict[str, tuple[str, str]]:
        mapping: dict[str, tuple[str, str]] = {}
        for domain in semantic_domains():
            label = DOMAIN_LABELS.get(domain.name, domain.name.replace("_", " ").title())
            for field in domain.fields:
                for raw_property in field.raw_properties:
                    mapping.setdefault(str(raw_property).lower(), (label, field.name))
        return mapping

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
    def _editor_kind(value_class: str, write_mode: str) -> str:
        if write_mode == "color" and value_class == "Color":
            return "color"
        if write_mode != "scalar":
            return "read_only"
        if value_class == "Boolean":
            return "bool"
        if value_class in {"Integer", "Integer64"}:
            return "int"
        if value_class in {"Float", "Double"}:
            return "float"
        if value_class == "String":
            return "string"
        return "read_only"

    def _property_rows(self, inventory: dict[str, Any]) -> tuple[PropertyRow, ...]:
        rows: list[PropertyRow] = []
        for item in inventory.get("properties") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            value_class = str(item.get("value_class") or "")
            write_mode = str(item.get("write_mode") or "read_only")
            domain, control = self._semantic_map.get(name.lower(), ("Other", "undeclared"))
            editor_kind = self._editor_kind(value_class, write_mode)
            rows.append(
                PropertyRow(
                    name=name,
                    value_class=value_class,
                    write_mode=write_mode,
                    readable=bool(item.get("readable")),
                    value=item.get("value"),
                    array_metadata=item.get("array_metadata") if isinstance(item.get("array_metadata"), dict) else None,
                    domain=domain,
                    control=control,
                    writable=editor_kind != "read_only",
                    editor_kind=editor_kind,
                )
            )
        return tuple(rows)

    def _sync_state_pending(self) -> None:
        self._state = replace(self._state, pending_edits=tuple(self._pending.values()))

    def _load_forest(self, forest_name: str, *, preflight: bool) -> ForestUIState:
        inventory = self.service.inventory(forest_name, preflight=preflight)
        properties = self._property_rows(inventory)
        units = self.service.scene_units(preflight=False)
        forests = self.service.list_forests(preflight=False)
        if forest_name not in forests:
            raise ForestControlError(f"Forest target became stale while loading UI state: {forest_name}")
        self._pending.clear()
        self._state = ForestUIState(
            forest_names=tuple(forests),
            selected_forest=forest_name,
            properties=properties,
            scene_units=self._unit_payload(units),
            pending_edits=(),
            artist_controls=self._artist_control_states(properties, self._unit_payload(units)),
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
                self._pending.clear()
                self._state = ForestUIState(
                    forest_names=(),
                    selected_forest=None,
                    properties=(),
                    scene_units=self._unit_payload(units),
                    pending_edits=(),
                    artist_controls=(),
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
                selected = self._state.selected_forest if self._state.selected_forest in forests else forests[0]
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


    @staticmethod
    def _display_distance_contract(scene_units: dict[str, Any] | None) -> tuple[float, str]:
        units = scene_units or {}
        display_unit = str(units.get("display_unit") or "").strip().lower()
        if display_unit in {"meter", "meters", "metre", "metres", "m"}:
            factor = float(units.get("one_meter_system_units") or 0.0)
            return (factor if factor > 0.0 else 1.0, "m")
        if display_unit in {"centimeter", "centimeters", "centimetre", "centimetres", "cm"}:
            factor = float(units.get("one_centimeter_system_units") or 0.0)
            return (factor if factor > 0.0 else 1.0, "cm")
        if display_unit in {"millimeter", "millimeters", "millimetre", "millimetres", "mm"}:
            factor = float(units.get("one_millimeter_system_units") or 0.0)
            return (factor if factor > 0.0 else 1.0, "mm")
        suffix = str(units.get("display_unit") or "").strip() or "units"
        return (1.0, suffix)

    @classmethod
    def _system_distance_to_display(cls, value: Any, scene_units: dict[str, Any] | None) -> tuple[float, str]:
        factor, suffix = cls._display_distance_contract(scene_units)
        return float(value) / factor, suffix

    @classmethod
    def _display_distance_to_system(cls, value: Any, scene_units: dict[str, Any] | None) -> float:
        factor, _suffix = cls._display_distance_contract(scene_units)
        return float(value) * factor

    def _infer_naturalness_choice(self, by_name: dict[str, PropertyRow]) -> str | None:
        for choice, profile in NATURALNESS_CANDIDATES.items():
            matched = True
            for property_name, expected in profile.items():
                row = by_name.get(property_name.lower())
                if row is None:
                    continue
                actual = row.value
                if isinstance(expected, float):
                    try:
                        if abs(float(actual) - float(expected)) > 1e-6:
                            matched = False
                            break
                    except Exception:
                        matched = False
                        break
                elif actual != expected:
                    matched = False
                    break
            if matched:
                return choice
        return None


    def _infer_cluster_character_choice(self, by_name: dict[str, PropertyRow]) -> str | None:
        units = self._state.scene_units
        for choice, profile in CLUSTER_CHARACTER_CANDIDATES.items():
            size_row = by_name.get("clusize")
            if size_row is None:
                continue
            expected_size = self._display_distance_to_system(profile["size_m"], units)
            try:
                if abs(float(size_row.value) - float(expected_size)) > 1e-6:
                    continue
            except Exception:
                continue
            matched = True
            for name in ("clurough", "clunoise", "cluedge"):
                row = by_name.get(name)
                if row is None:
                    continue
                try:
                    if abs(float(row.value) - float(profile[name])) > 1e-6:
                        matched = False
                        break
                except Exception:
                    matched = False
                    break
            if matched:
                return choice
        return None

    def _artist_control_states(
        self,
        properties: tuple[PropertyRow, ...],
        scene_units: dict[str, Any] | None = None,
    ) -> tuple[ArtistControlState, ...]:
        by_name = {row.name.lower(): row for row in properties}
        units = scene_units if scene_units is not None else self._state.scene_units
        pending_names = {name.lower() for name in self._pending}
        states: list[ArtistControlState] = []
        for spec in artist_control_specs():
            affected = tuple(name for name in spec.dependent_properties if name.lower() in by_name)
            available = False
            value = self._artist_values.get(spec.key)
            display_suffix = ""
            calibration_status = "calibration_required"

            if spec.key == "density_spacing":
                x = by_name.get("units_x")
                y = by_name.get("units_y")
                if x is not None and y is not None:
                    try:
                        if not ({"units_x", "units_y"} & pending_names) and abs(float(x.value) - float(y.value)) < 1e-9:
                            value, display_suffix = self._system_distance_to_display(x.value, units)
                            self._artist_values[spec.key] = value
                        else:
                            _factor, display_suffix = self._display_distance_contract(units)
                    except Exception:
                        value = None
                else:
                    _factor, display_suffix = self._display_distance_contract(units)
                available = x is not None and y is not None and bool(x.writable and y.writable)
                calibration_status = "active" if available else "blocked"

            elif spec.key == "naturalness":
                naturalness_properties = {name.lower() for name in NATURALNESS_CANDIDATES["Natural"]}
                has_pending_naturalness = bool(naturalness_properties & pending_names)
                if not has_pending_naturalness:
                    inferred = self._infer_naturalness_choice(by_name)
                    if inferred is not None:
                        value = inferred
                        self._artist_values[spec.key] = inferred
                required_rows = [by_name.get(name.lower()) for name in NATURALNESS_CANDIDATES["Natural"]]
                present_rows = [row for row in required_rows if row is not None]
                available = bool(present_rows) and all(row.writable for row in present_rows)
                calibration_status = "active" if available else "blocked"

            elif spec.key == "cluster_character":
                cluster_properties = {"clusize", "clurough", "clunoise", "cluedge"}
                has_pending_cluster = bool(cluster_properties & pending_names)
                if not has_pending_cluster:
                    inferred = self._infer_cluster_character_choice(by_name)
                    if inferred is not None:
                        value = inferred
                        self._artist_values[spec.key] = inferred
                required_rows = [by_name.get(name) for name in ("clusize", "clurough", "clunoise", "cluedge")]
                present_rows = [row for row in required_rows if row is not None]
                available = len(present_rows) == 4 and all(row.writable for row in present_rows)
                calibration_status = "active" if available else "blocked"

            elif spec.key == "variation":
                available = False
                calibration_status = "blocked_by_capability"

            states.append(ArtistControlState(
                key=spec.key, label=spec.label, kind=spec.kind, value=value,
                description=spec.description, dependent_properties=spec.dependent_properties,
                direct_write=spec.direct_write, available=available, affected_properties=affected,
                display_suffix=display_suffix, calibration_status=calibration_status,
            ))
        return tuple(states)

    def _set_naturalness_control(self, choice: str) -> ForestUIState:
        plan = SemanticCalibrationPlanner(self).plan("naturalness", choice)
        if not plan.executable:
            detail = ", ".join(plan.blocked_reasons) or "no executable operations"
            raise ForestControlError(f"Naturalness is not available on this Forest: {detail}")

        self._artist_values["naturalness"] = choice
        for operation in plan.operations:
            row = self._row_by_name(operation.property_name)
            parsed = self.parse_editor_value(row, operation.value)
            if parsed == row.value:
                self._pending.pop(row.name, None)
            else:
                self._pending[row.name] = PendingEdit(row.name, row.value, parsed, row.editor_kind)

        self._state = replace(
            self._state,
            pending_edits=tuple(self._pending.values()),
            artist_controls=self._artist_control_states(self._state.properties, self._state.scene_units),
            status=f"Naturalness: {choice}",
            error=None,
        )
        return self._state


    def _set_cluster_character_control(self, choice: str) -> ForestUIState:
        plan = SemanticCalibrationPlanner(self).plan("cluster_character", choice)
        if not plan.executable:
            detail = ", ".join(plan.blocked_reasons) or "no executable operations"
            raise ForestControlError(f"Cluster Character is not available on this Forest: {detail}")
        self._artist_values["cluster_character"] = choice
        for operation in plan.operations:
            row = self._row_by_name(operation.property_name)
            parsed = self.parse_editor_value(row, operation.value)
            if parsed == row.value:
                self._pending.pop(row.name, None)
            else:
                self._pending[row.name] = PendingEdit(row.name, row.value, parsed, row.editor_kind)
        self._state = replace(
            self._state,
            pending_edits=tuple(self._pending.values()),
            artist_controls=self._artist_control_states(self._state.properties, self._state.scene_units),
            status=f"Cluster Character: {choice}",
            error=None,
        )
        return self._state

    def set_artist_control(self, key: str, value: Any) -> ForestUIState:
        try:
            specs = {spec.key: spec for spec in artist_control_specs()}
            if key not in specs:
                raise ForestControlError(f"Unknown artist control: {key}")
            spec = specs[key]
            if spec.kind == "choice":
                token = str(value)
                if token not in spec.options:
                    raise ForestControlError(f"Invalid artist control value for {spec.label}: {token}")
                if key == "naturalness":
                    return self._set_naturalness_control(token)
                if key == "cluster_character":
                    return self._set_cluster_character_control(token)
                if key == "variation":
                    raise ForestControlError("Variation is not available until its Forest Pack activation flags are writable.")
                raise ForestControlError(f"{spec.label} is not calibrated yet.")
            if key == "density_spacing":
                try:
                    spacing = float(str(value).replace(",", "."))
                except Exception as exc:
                    raise ForestControlError("Plant Spacing requires a positive numeric value.") from exc
                if spacing <= 0.0:
                    raise ForestControlError("Plant Spacing must be greater than zero.")
                rows = {row.name.lower(): row for row in self._state.properties}
                targets = [rows.get("units_x"), rows.get("units_y")]
                if any(row is None for row in targets):
                    raise ForestControlError("Plant Spacing requires units_x and units_y on the selected Forest.")
                if any(not row.writable for row in targets if row is not None):
                    raise ForestControlError("Plant Spacing cannot be edited because its synchronized raw properties are not writable.")
                raw_spacing = self._display_distance_to_system(spacing, self._state.scene_units)
                self._artist_values[key] = spacing
                for row in targets:
                    assert row is not None
                    parsed = self.parse_editor_value(row, raw_spacing)
                    if parsed == row.value:
                        self._pending.pop(row.name, None)
                    else:
                        self._pending[row.name] = PendingEdit(row.name, row.value, parsed, row.editor_kind)
                _factor, suffix = self._display_distance_contract(self._state.scene_units)
                self._state = replace(
                    self._state,
                    pending_edits=tuple(self._pending.values()),
                    artist_controls=self._artist_control_states(self._state.properties, self._state.scene_units),
                    status=f"Plant Spacing: {spacing:g} {suffix}",
                    error=None,
                )
                return self._state
            raise ForestControlError(f"Unsupported artist control kind: {spec.kind}")
        except Exception as exc:
            self._state = replace(self._state, status="Artist control rejected", error=f"{type(exc).__name__}: {exc}")
            return self._state


    def semantic_calibration_snapshot(self) -> dict[str, Any]:
        forest_name = self._state.selected_forest
        if not forest_name:
            raise ForestControlError("No Forest selected for semantic calibration snapshot.")
        by_name = {row.name.lower(): row for row in self._state.properties}
        result: dict[str, Any] = {
            "forest_name": forest_name,
            "scene_units": dict(self._state.scene_units or {}),
            "controls": {},
            "read_only": True,
        }
        specs = {spec.key: spec for spec in artist_control_specs()}
        for key in calibration_probe_keys():
            spec = specs[key]
            properties: list[dict[str, Any]] = []
            for name in spec.dependent_properties:
                row = by_name.get(name.lower())
                if row is None:
                    continue
                properties.append({
                    "name": row.name,
                    "value": row.value,
                    "value_class": row.value_class,
                    "write_mode": row.write_mode,
                    "writable": row.writable,
                    "domain": row.domain,
                    "control": row.control,
                })
            result["controls"][key] = {
                "label": spec.label,
                "dependent_properties": list(spec.dependent_properties),
                "available_properties": properties,
                "available_count": len(properties),
            }
        return result

    def rows_for_domain(self, domain_label: str) -> tuple[PropertyRow, ...]:
        if domain_label == "All Properties":
            return self._state.properties
        return tuple(row for row in self._state.properties if row.domain == domain_label)

    def _row_by_name(self, property_name: str) -> PropertyRow:
        for row in self._state.properties:
            if row.name == property_name:
                return row
        raise ForestControlError(f"UI property is stale or missing: {property_name}")

    @staticmethod
    def parse_editor_value(row: PropertyRow, value: Any) -> Any:
        if not row.writable:
            raise ForestControlError(f"UI property is read-only: {row.name}")
        if row.editor_kind == "bool":
            if isinstance(value, bool):
                return value
            token = str(value).strip().lower()
            if token in {"true", "1", "yes", "on"}:
                return True
            if token in {"false", "0", "no", "off"}:
                return False
            raise ForestControlError(f"Boolean value expected for {row.name}.")
        if row.editor_kind == "int":
            if isinstance(value, bool):
                raise ForestControlError(f"Integer value expected for {row.name}.")
            try:
                return int(str(value).strip())
            except Exception as exc:
                raise ForestControlError(f"Integer value expected for {row.name}.") from exc
        if row.editor_kind == "float":
            if isinstance(value, bool):
                raise ForestControlError(f"Numeric value expected for {row.name}.")
            try:
                return float(str(value).strip().replace(",", "."))
            except Exception as exc:
                raise ForestControlError(f"Numeric value expected for {row.name}.") from exc
        if row.editor_kind == "string":
            return str(value)
        if row.editor_kind == "color":
            if isinstance(value, (list, tuple)):
                parts = list(value)
            else:
                parts = [part.strip() for part in str(value).split(",")]
            if len(parts) != 3:
                raise ForestControlError(f"RGB color requires three components for {row.name}.")
            try:
                color = [float(part) for part in parts]
            except Exception as exc:
                raise ForestControlError(f"RGB color requires numeric components for {row.name}.") from exc
            if any(component < 0.0 or component > 255.0 for component in color):
                raise ForestControlError(f"RGB color components must be in the 0..255 range for {row.name}.")
            return color
        raise ForestControlError(f"Unsupported UI editor for {row.name}: {row.editor_kind}")

    def set_pending_value(self, property_name: str, value: Any) -> ForestUIState:
        try:
            row = self._row_by_name(property_name)
            parsed = self.parse_editor_value(row, value)
            if parsed == row.value:
                self._pending.pop(property_name, None)
            else:
                self._pending[property_name] = PendingEdit(property_name, row.value, parsed, row.editor_kind)
            self._state = replace(
                self._state,
                pending_edits=tuple(self._pending.values()),
                status=f"{len(self._pending)} pending change(s)" if self._pending else f"Loaded {self._state.selected_forest}",
                error=None,
            )
            return self._state
        except Exception as exc:
            self._state = replace(self._state, status="Property edit rejected", error=f"{type(exc).__name__}: {exc}")
            return self._state

    def revert_pending(self) -> ForestUIState:
        self._pending.clear()
        self._state = replace(
            self._state,
            pending_edits=(),
            artist_controls=self._artist_control_states(self._state.properties, self._state.scene_units),
            status=f"Pending edits reverted for {self._state.selected_forest}" if self._state.selected_forest else "Pending edits reverted",
            error=None,
        )
        return self._state

    def apply_pending(self) -> ForestUIState:
        try:
            forest_name = self._state.selected_forest
            if not forest_name:
                raise ForestControlError("No Forest selected.")
            if not self._pending:
                raise ForestControlError("There are no pending Forest changes to apply.")
            forests = self.service.list_forests(preflight=True)
            if forest_name not in forests:
                raise ForestControlError(f"Selected Forest became stale before Apply: {forest_name}")
            operations = tuple(
                UnifiedControlOperation(property_name=edit.property_name, value=edit.value, label="ui")
                for edit in self._pending.values()
            )
            result = self.transaction_manager.execute(
                operations,
                default_forest_name=forest_name,
                rollback_on_success=False,
            )
            if not result.write_verified:
                raise ForestControlError("UI transaction did not verify all writes.")
            state = self._load_forest(forest_name, preflight=False)
            self._state = replace(state, status=f"Applied {result.operation_count} change(s) to {forest_name}")
            return self._state
        except Exception as exc:
            self._state = replace(self._state, status="Apply failed", error=f"{type(exc).__name__}: {exc}")
            return self._state
