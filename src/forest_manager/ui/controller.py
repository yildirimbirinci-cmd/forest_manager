from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from forest_manager.forest_control.schema import semantic_domains
from forest_manager.forest_control.service import ForestControlError, ForestPackControlService
from forest_manager.forest_control.unit_conversion import UnitConversionGateway
from forest_manager.forest_control.plant_group_execution import (
    refresh_plant_group_distribution_fast,
    refresh_plant_group_diversity_map,
)
from forest_manager.forest_control.scene_runtime import ForestSceneRuntime
from forest_manager.forest_control.scene_state import SceneStateGateway
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
from .plant_groups import (
    PlantGroupTarget,
    discover_plant_groups,
    discover_primary_forest,
    find_group_for_forest,
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
    primary_forest: str | None = None
    plant_groups: tuple[PlantGroupTarget, ...] = ()
    selected_group_id: str | None = None
    selected_group_label: str | None = None
    selected_forest: str | None = None
    properties: tuple[PropertyRow, ...] = ()
    scene_units: dict[str, Any] | None = None
    pending_edits: tuple[PendingEdit, ...] = ()
    artist_controls: tuple[ArtistControlState, ...] = ()
    selected_group_runtime: dict[str, Any] | None = None
    bridge_online: bool = False
    status: str = "Not connected"
    error: str | None = None


class ForestManagerUIController:
    """Stage 7 UI controller over the verified Stage 6 production backend."""

    def __init__(
        self,
        service: ForestPackControlService | None = None,
        transaction_manager: UnifiedControlTransactionManager | None = None,
        scene_runtime: ForestSceneRuntime | None = None,
        scene_state: SceneStateGateway | None = None,
    ) -> None:
        self.service = service or ForestPackControlService()
        self.transaction_manager = transaction_manager or UnifiedControlTransactionManager(self.service)
        self.scene_runtime = scene_runtime or ForestSceneRuntime(service=self.service)
        self.scene_state = scene_state or SceneStateGateway(self.service)
        self._state = ForestUIState()
        self._pending: dict[str, PendingEdit] = {}
        self._semantic_map = self._build_semantic_map()
        self._artist_values = default_artist_values()
        # Selection-time cache. Forest/Plant Group switching must never trigger
        # a full Forest Pack inventory/readback on the Qt UI thread.
        self._group_runtime_cache: dict[str, dict[str, Any]] = {}

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

    def _canonical_group_reset_defaults(self, target: dict[str, Any]) -> dict[str, Any]:
        """Return Reset defaults calibrated to the current active Area size.

        Older Stage 7 builds could persist a *new* area_reference_system while
        leaving the child spacing at the legacy 75/75/25 m values.  Merely
        comparing the stored area reference therefore is not enough.  A reset
        baseline is valid only when both the area reference and the spacing
        itself agree with the current-area calibration.
        """
        existing = target.get("reset_defaults")
        group_id = str(target.get("group_id") or "").lower()

        current_extent = 0.0
        try:
            forest_name = self._state.selected_forest or "FM_Forest_001"
            bounds = self.service.single_forest_area_bounds(forest_name, preflight=False)
            current_extent = min(
                float(bounds.get("width_system") or 0.0),
                float(bounds.get("height_system") or 0.0),
            )
        except Exception:
            current_extent = 0.0

        authored_spacing_m = 25.0 if "structural_shrub" in group_id else 75.0
        one_meter, _suffix = self._display_distance_contract(self._state.scene_units)
        if current_extent > 0.0 and one_meter > 0.0:
            authored_extent_system = 75.0 * one_meter
            scale = current_extent / authored_extent_system
            expected_spacing = max(1e-6, authored_spacing_m * one_meter * scale)
        else:
            expected_spacing = self._display_distance_to_system(authored_spacing_m, self._state.scene_units)

        if isinstance(existing, dict):
            spacing = existing.get("spacing_system")
            artist = existing.get("artist_values")
            stored_extent = float(existing.get("area_reference_system") or 0.0)
            extent_matches = (
                current_extent <= 0.0
                or (stored_extent > 0.0 and abs(stored_extent - current_extent) <= max(1.0, current_extent * 0.02))
            )
            stored_spacing = (
                float(spacing[0])
                if isinstance(spacing, (list, tuple)) and len(spacing) == 2
                else 0.0
            )
            spacing_matches = (
                expected_spacing <= 0.0
                or abs(stored_spacing - expected_spacing) <= max(1.0, expected_spacing * 0.02)
            )
            if isinstance(artist, dict) and extent_matches and spacing_matches:
                if "species_scale_percent" not in artist:
                    artist["species_scale_percent"] = 100.0
                return existing

        defaults = {
            "spacing_system": [float(expected_spacing), float(expected_spacing)],
            "area_reference_system": float(current_extent),
            "artist_values": {
                "species_enabled": True,
                "species_scale_percent": 100.0,
                "naturalness": "Balanced",
                "cluster_character": "Medium Clusters",
            },
        }
        target["reset_defaults"] = defaults
        return defaults

    def _synchronize_group_manifest_from_scene(self, manifest: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        """Merge live Forest runtime state into the scene-persisted semantic manifest.

        The 3ds Max scene is authoritative for runtime-editable state.  In
        particular, per-species spacing is reconstructed from each Geometry
        item's Collision Radius so closing/reopening Forest Manager does not
        silently restore stale manifest values.
        """
        raw_groups = manifest.get("groups") if isinstance(manifest, dict) else None
        if not isinstance(raw_groups, list):
            return manifest, False
        changed = False
        groups_by_id = {group.group_id: group for group in self._state.plant_groups if group.manifest_backed}
        for target in raw_groups:
            if not isinstance(target, dict):
                continue
            group_id = str(target.get("group_id") or "")
            group = groups_by_id.get(group_id)
            if group is None:
                continue
            if not isinstance(target.get("reset_defaults"), dict):
                self._canonical_group_reset_defaults(target)
                changed = True
            artist_values = target.get("artist_values")
            if not isinstance(artist_values, dict):
                artist_values = {}
                target["artist_values"] = artist_values
                changed = True
            try:
                indices = self._group_geometry_indices(group)
                enabled = all(
                    int(self.service.get_array_element(group.forest_name, "geomlist", index, preflight=False).get("value") or 0) != 0
                    for index in indices
                )
                if artist_values.get("species_enabled") is not enabled:
                    artist_values["species_enabled"] = enabled
                    changed = True

                # Reconstruct the currently applied Plant Spacing from the
                # live ForestPack Geometry Collision Radius.  The reset
                # baseline is persisted in the Max scene manifest; radius=100
                # means exactly that authored baseline.
                defaults = self._canonical_group_reset_defaults(target)
                reset_pair = defaults.get("spacing_system") if isinstance(defaults, dict) else None
                if isinstance(reset_pair, (list, tuple)) and reset_pair:
                    baseline = float(reset_pair[0])
                    radii: list[float] = []
                    for index in indices:
                        radius = float(
                            self.service.get_array_element(
                                group.forest_name, "radiuslist", index, preflight=False
                            ).get("value")
                            or 100.0
                        )
                        if radius > 0.0:
                            radii.append(radius)
                    if radii and baseline > 0.0:
                        live_spacing = baseline * (sum(radii) / len(radii)) / 100.0
                        current_pair = target.get("spacing_system")
                        current_spacing = (
                            float(current_pair[0])
                            if isinstance(current_pair, (list, tuple)) and current_pair
                            else None
                        )
                        if current_spacing is None or abs(current_spacing - live_spacing) > 1e-6:
                            target["spacing_system"] = [float(live_spacing), float(live_spacing)]
                            try:
                                display_spacing, _ = self._system_distance_to_display(
                                    float(live_spacing), self._state.scene_units
                                )
                                artist_values["density_spacing"] = float(display_spacing)
                            except Exception:
                                artist_values.pop("density_spacing", None)
                            changed = True
            except Exception:
                pass
        return manifest, changed


    def _prime_group_runtime_cache(self, manifest: dict[str, Any], groups: tuple[PlantGroupTarget, ...]) -> None:
        """Build lightweight Plant Group UI state from the already-loaded manifest.

        This cache is deliberately scene-read free.  The expensive live Forest Pack
        readback is reserved for Refresh Scene / Apply / Reset, not tree selection.
        """
        raw_groups = manifest.get("groups") if isinstance(manifest, dict) else None
        by_id = {
            str(item.get("group_id") or ""): item
            for item in (raw_groups or [])
            if isinstance(item, dict) and str(item.get("group_id") or "").strip()
        }
        for group in groups:
            target = by_id.get(group.group_id) or {}
            artist = target.get("artist_values") if isinstance(target.get("artist_values"), dict) else {}
            spacing_pair = target.get("spacing_system")
            spacing_display = None
            spacing_suffix = ""
            if isinstance(spacing_pair, (list, tuple)) and spacing_pair:
                try:
                    spacing_display, spacing_suffix = self._system_distance_to_display(
                        float(spacing_pair[0]), self._state.scene_units
                    )
                except Exception:
                    spacing_display = None
                    spacing_suffix = ""
            self._group_runtime_cache[group.group_id] = {
                "geometry_indices": [],
                "source_names": [str(value) for value in (target.get("source_names") or []) if str(value).strip()],
                "enabled": bool(artist.get("species_enabled", True)),
                "scale_percent": float(artist.get("species_scale_percent", 100.0) or 100.0),
                "probability_percent": float(artist.get("species_probability_percent", 0.0) or 0.0),
                "spacing": spacing_display,
                "spacing_suffix": spacing_suffix,
            }

    def _select_group_from_cache(self, group: PlantGroupTarget) -> ForestUIState:
        runtime = dict(self._group_runtime_cache.get(group.group_id) or {})
        self._state = replace(
            self._state,
            selected_group_id=group.group_id,
            selected_group_label=group.label,
            selected_forest=group.forest_name,
            selected_group_runtime=runtime or None,
            artist_controls=self._artist_control_states(
                self._state.properties, self._state.scene_units, group
            ),
            status=f"Loaded {group.label}",
            error=None,
        )
        return self._state

    def _load_forest(self, forest_name: str, *, preflight: bool, selected_group_id: str | None = None) -> ForestUIState:
        inventory = self.service.inventory(forest_name, preflight=preflight)
        properties = self._property_rows(inventory)
        units = self.service.scene_units(preflight=False)
        forests = self.service.list_forests(preflight=False)
        if forest_name not in forests:
            raise ForestControlError(f"Forest target became stale while loading UI state: {forest_name}")
        self._pending.clear()
        try:
            group_manifest = self.scene_state.read_manifest(preflight=False)
        except Exception:
            group_manifest = {}
        groups = discover_plant_groups(forests, group_manifest)
        self._prime_group_runtime_cache(group_manifest, groups)
        group = None
        if selected_group_id:
            group = next((item for item in groups if item.group_id == selected_group_id), None)
        elif self._state.selected_group_id:
            group = next((item for item in groups if item.group_id == self._state.selected_group_id), None)
        if group is None and not any(item.manifest_backed for item in groups):
            group = find_group_for_forest(groups, forest_name)
        self._state = ForestUIState(
            forest_names=tuple(forests),
            primary_forest=discover_primary_forest(forests),
            plant_groups=groups,
            selected_group_id=group.group_id if group is not None else None,
            selected_group_label=group.label if group is not None else None,
            selected_forest=forest_name,
            properties=properties,
            scene_units=self._unit_payload(units),
            pending_edits=(),
            artist_controls=self._artist_control_states(properties, self._unit_payload(units), group),
            selected_group_runtime=None,
            bridge_online=True,
            status=(
                f"Loaded plant group {group.label}: {len(properties)} properties"
                if group is not None
                else f"Loaded global planting target: {len(properties)} properties"
            ),
            error=None,
        )
        synced_manifest, manifest_changed = self._synchronize_group_manifest_from_scene(group_manifest)
        if manifest_changed:
            try:
                self.scene_state.write_verified(synced_manifest, preflight=False)
                manifest_write_verified = True
            except ForestControlError:
                manifest_write_verified = False
            if manifest_write_verified:
                groups = discover_plant_groups(forests, synced_manifest)
                self._prime_group_runtime_cache(synced_manifest, groups)
                group = next((item for item in groups if item.group_id == self._state.selected_group_id), None)
                self._state = replace(
                    self._state,
                    plant_groups=groups,
                    selected_group_label=group.label if group is not None else None,
                    artist_controls=self._artist_control_states(properties, self._unit_payload(units), group),
                )
        if group is not None and group.manifest_backed:
            runtime = self._read_selected_group_runtime(group)
            if runtime:
                self._group_runtime_cache[group.group_id] = dict(runtime)
            self._state = replace(self._state, selected_group_runtime=runtime)
        return self._state

    def refresh_scene(self, *, prefer_max_selection: bool = True) -> ForestUIState:
        try:
            forests = self.service.list_forests(preflight=True)
            units = self.service.scene_units(preflight=False)
            if not forests:
                self._pending.clear()
                self._state = ForestUIState(
                    forest_names=(),
                    primary_forest=None,
                    plant_groups=(),
                    selected_group_id=None,
                    selected_group_label=None,
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

    def select_plant_group(self, group_id: str) -> ForestUIState:
        """Switch the editor target without touching 3ds Max.

        Scene synchronization happens on Refresh Scene / Apply / Reset.  Tree
        navigation is intentionally cache-only so Qt never blocks on bridge I/O.
        """
        try:
            candidate = str(group_id or "").strip()
            group = next((item for item in self._state.plant_groups if item.group_id == candidate), None)
            if group is None:
                raise ForestControlError(f"Plant group is stale or missing: {candidate}")
            return self._select_group_from_cache(group)
        except Exception as exc:
            self._state = replace(
                self._state,
                status="Plant group selection failed",
                error=f"{type(exc).__name__}: {exc}",
            )
            return self._state

    def select_global_planting(self) -> ForestUIState:
        """Select Forest 01 using the existing in-memory scene snapshot only."""
        target = self._state.primary_forest
        if not target:
            self._state = replace(
                self._state,
                status="Global planting target unavailable",
                error="ForestControlError: No primary Forest is available.",
            )
            return self._state
        self._state = replace(
            self._state,
            selected_group_id=None,
            selected_group_label=None,
            selected_forest=target,
            selected_group_runtime=None,
            artist_controls=self._artist_control_states(
                self._state.properties, self._state.scene_units, None
            ),
            status="Loaded Forest 01",
            error=None,
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
        contract = UnitConversionGateway.display_contract(scene_units)
        return contract.system_units_per_display_unit, contract.suffix

    @staticmethod
    def _system_distance_to_display(value: Any, scene_units: dict[str, Any] | None) -> tuple[float, str]:
        return UnitConversionGateway.system_to_display(value, scene_units)

    @staticmethod
    def _display_distance_to_system(value: Any, scene_units: dict[str, Any] | None) -> float:
        return UnitConversionGateway.display_to_system(value, scene_units)

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
        group: PlantGroupTarget | None = None,
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

            if group is not None and group.manifest_backed:
                pending_key = self._group_pending_key(group.group_id, spec.key)
                pending_edit = self._pending.get(pending_key)
                if pending_edit is not None:
                    value = pending_edit.value
                elif spec.key == "density_spacing" and group.spacing_system is not None:
                    gx, gy = group.spacing_system
                    if abs(float(gx) - float(gy)) < 1e-9:
                        value, display_suffix = self._system_distance_to_display(gx, units)
                elif spec.key in group.artist_values:
                    value = group.artist_values[spec.key]

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
            artist_controls=self._artist_control_states(self._state.properties, self._state.scene_units, self._selected_plant_group()),
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
            artist_controls=self._artist_control_states(self._state.properties, self._state.scene_units, self._selected_plant_group()),
            status=f"Cluster Character: {choice}",
            error=None,
        )
        return self._state


    def _manifest_group_payload(self, group: PlantGroupTarget) -> dict[str, Any]:
        _manifest, target = self.scene_state.read_group(group.group_id, preflight=False)
        return target

    def _group_geometry_indices(self, group: PlantGroupTarget) -> tuple[int, ...]:
        target = self._manifest_group_payload(group)
        source_names = {str(value) for value in (target.get("source_names") or []) if str(value).strip()}
        if not source_names:
            raise ForestControlError(f"Plant group has no Geometry source assignment: {group.group_id}")
        row = next((item for item in self._state.properties if item.name.lower() == "namelist"), None)
        metadata = row.array_metadata if row is not None else None
        count = int((metadata or {}).get("count") or 0) if isinstance(metadata, dict) else 0
        if count <= 0:
            inventory = self.service.inventory(group.forest_name, preflight=False)
            item = next(
                (prop for prop in (inventory.get("properties") or []) if isinstance(prop, dict) and str(prop.get("name") or "").lower() == "namelist"),
                None,
            )
            item_metadata = item.get("array_metadata") if isinstance(item, dict) else None
            count = int((item_metadata or {}).get("count") or 0) if isinstance(item_metadata, dict) else 0
        matches: list[int] = []
        for index in range(count):
            data = self.service.get_array_element(group.forest_name, "namelist", index, preflight=False)
            if str(data.get("value") or "") in source_names:
                matches.append(index)
        if not matches:
            raise ForestControlError(f"Plant group Geometry source was not found in {group.forest_name}: {group.group_id}")
        return tuple(matches)

    def _read_selected_group_runtime(self, group: PlantGroupTarget | None) -> dict[str, Any] | None:
        if group is None or not group.manifest_backed:
            return None
        target = self._manifest_group_payload(group)
        indices = self._group_geometry_indices(group)
        enabled_values: list[bool] = []
        scales: list[float] = []
        probabilities: list[float] = []
        for index in indices:
            enabled_values.append(int(self.service.get_array_element(group.forest_name, "geomlist", index, preflight=False).get("value") or 0) != 0)
            scales.append(float(self.service.get_array_element(group.forest_name, "ScaleList", index, preflight=False).get("value") or 0.0))
            probabilities.append(float(self.service.get_array_element(group.forest_name, "problist", index, preflight=False).get("value") or 0.0))
        spacing_pair = target.get("spacing_system")
        spacing_display = None
        spacing_suffix = ""
        if isinstance(spacing_pair, (list, tuple)) and spacing_pair:
            spacing_display, spacing_suffix = self._system_distance_to_display(float(spacing_pair[0]), self._state.scene_units)
        artist_values = target.get("artist_values") if isinstance(target.get("artist_values"), dict) else {}
        stored_scale = artist_values.get("species_scale_percent") if isinstance(artist_values, dict) else None
        return {
            "geometry_indices": list(indices),
            "source_names": [str(value) for value in (target.get("source_names") or []) if str(value).strip()],
            "enabled": all(enabled_values),
            "scale_percent": float(stored_scale) if stored_scale is not None else (scales[0] if scales else 100.0),
            "probability_percent": probabilities[0] if probabilities else 0.0,
            "spacing": spacing_display,
            "spacing_suffix": spacing_suffix,
        }

    def _refresh_selected_group_runtime_state(self, group: PlantGroupTarget) -> ForestUIState:
        runtime = self._read_selected_group_runtime(group)
        self._state = replace(self._state, selected_group_runtime=runtime)
        return self._state

    @staticmethod
    def _group_pending_key(group_id: str, field: str) -> str:
        return f"__plant_group__|{group_id}|{field}"

    def _selected_group_runtime_cached(self, group: PlantGroupTarget) -> dict[str, Any]:
        if self._state.selected_group_id == group.group_id and self._state.selected_group_runtime:
            return dict(self._state.selected_group_runtime)
        runtime = self._read_selected_group_runtime(group)
        return dict(runtime or {})

    def _stage_group_artist_edit(
        self, group: PlantGroupTarget, field: str, value: Any, editor_kind: str
    ) -> ForestUIState:
        original_value = group.artist_values.get(field)
        key = self._group_pending_key(group.group_id, field)
        if value == original_value:
            self._pending.pop(key, None)
        else:
            self._pending[key] = PendingEdit(key, original_value, value, editor_kind)
        self._artist_values[field] = value
        self._state = replace(
            self._state,
            pending_edits=tuple(self._pending.values()),
            artist_controls=self._artist_control_states(
                self._state.properties, self._state.scene_units, self._selected_plant_group()
            ),
            status=f"{len(self._pending)} pending change(s)" if self._pending else f"Loaded {group.label}",
            error=None,
        )
        return self._state

    def _stage_all_groups_artist_edit(self, field: str, value: Any, editor_kind: str) -> ForestUIState:
        groups = tuple(group for group in self._state.plant_groups if group.manifest_backed)
        if not groups:
            raise ForestControlError("Forest 01 has no manifest-backed Plant Groups.")
        for group in groups:
            original_value = group.artist_values.get(field)
            key = self._group_pending_key(group.group_id, field)
            if value == original_value:
                self._pending.pop(key, None)
            else:
                self._pending[key] = PendingEdit(key, original_value, value, editor_kind)
        self._artist_values[field] = value
        self._state = replace(
            self._state,
            pending_edits=tuple(self._pending.values()),
            artist_controls=self._artist_control_states(
                self._state.properties, self._state.scene_units, None
            ),
            status=(
                f"Forest 01: {field.replace('_', ' ').title()} staged for {len(groups)} Plant Groups"
                if self._pending
                else "Loaded Forest 01"
            ),
            error=None,
        )
        return self._state

    def _persist_group_runtime_value(self, group: PlantGroupTarget, field: str, value: Any) -> None:
        manifest, target = self.scene_state.read_group(group.group_id, preflight=False)
        artist_values = target.get("artist_values")
        if not isinstance(artist_values, dict):
            artist_values = {}
            target["artist_values"] = artist_values
        key = {
            "enabled": "species_enabled",
            "scale": "species_scale_percent",
            "probability": "species_probability_percent",
        }[field]
        artist_values[key] = value
        self.scene_state.write_verified(
            manifest,
            preflight=False,
            error_message="Plant-group live setting write was not verified.",
        )

    def _apply_group_runtime_live(self, group: PlantGroupTarget, field: str, value: Any) -> ForestUIState:
        indices = self._group_geometry_indices(group)
        species_ids: list[int] = []
        for index in indices:
            species_id = int(
                self.service.get_array_element(
                    group.forest_name, "specidlist", index, preflight=False
                ).get("value")
                or 0
            )
            if species_id > 0:
                species_ids.append(species_id)
        if not species_ids:
            raise ForestControlError(f"Plant Group species IDs could not be resolved: {group.group_id}")

        kwargs: dict[str, Any] = {}
        if field == "enabled":
            kwargs["enabled"] = bool(value)
        elif field == "scale":
            kwargs["scale_percent"] = float(value)
        elif field == "probability":
            kwargs["probability_percent"] = float(value)
        else:
            raise ForestControlError(f"Unsupported live Plant Group field: {field}")

        result = self.service.apply_plant_group_species_runtime(group.forest_name, species_ids, preflight=False, **kwargs)
        if result.get("verified") is not True:
            raise ForestControlError(f"Plant Group live {field} update was not verified.")
        self._persist_group_runtime_value(group, field, value)

        runtime = dict(self._state.selected_group_runtime or {})
        runtime_key = {
            "enabled": "enabled",
            "scale": "scale_percent",
            "probability": "probability_percent",
        }[field]
        runtime[runtime_key] = value
        self._group_runtime_cache[group.group_id] = dict(runtime)
        pending_key = self._group_pending_key(group.group_id, field)
        self._pending.pop(pending_key, None)
        self._state = replace(
            self._state,
            selected_group_runtime=runtime,
            pending_edits=tuple(self._pending.values()),
            status=f"{group.label}: {field.replace('_', ' ').title()} live synced to 3ds Max",
            error=None,
        )
        return self._state

    def _stage_group_edit(
        self, group: PlantGroupTarget, field: str, original_value: Any, value: Any, editor_kind: str
    ) -> ForestUIState:
        key = self._group_pending_key(group.group_id, field)
        if value == original_value:
            self._pending.pop(key, None)
        else:
            self._pending[key] = PendingEdit(key, original_value, value, editor_kind)
        runtime = dict(self._state.selected_group_runtime or {})
        runtime_key = {
            "enabled": "enabled",
            "scale": "scale_percent",
            "probability": "probability_percent",
        }[field]
        runtime[runtime_key] = value
        self._group_runtime_cache[group.group_id] = dict(runtime)
        self._state = replace(
            self._state,
            selected_group_runtime=runtime,
            pending_edits=tuple(self._pending.values()),
            status=f"{len(self._pending)} pending change(s)" if self._pending else f"Loaded {group.label}",
            error=None,
        )
        return self._state

    def set_selected_group_enabled(self, enabled: bool) -> ForestUIState:
        try:
            group = self._selected_plant_group()
            if group is None or not group.manifest_backed:
                raise ForestControlError("Select a Plant Group before changing species visibility.")
            return self._apply_group_runtime_live(group, "enabled", bool(enabled))
        except Exception as exc:
            self._state = replace(self._state, status="Plant Group visibility edit rejected", error=f"{type(exc).__name__}: {exc}")
            return self._state

    def set_selected_group_scale(self, percent: Any) -> ForestUIState:
        try:
            value = float(str(percent).replace(",", "."))
            if value <= 0.0:
                raise ForestControlError("Plant Group scale must be greater than zero.")
            group = self._selected_plant_group()
            if group is None or not group.manifest_backed:
                raise ForestControlError("Select a Plant Group before changing species scale.")
            return self._apply_group_runtime_live(group, "scale", value)
        except Exception as exc:
            self._state = replace(self._state, status="Plant Group scale edit rejected", error=f"{type(exc).__name__}: {exc}")
            return self._state

    def set_selected_group_probability(self, percent: Any) -> ForestUIState:
        try:
            value = float(str(percent).replace(",", "."))
            if value < 0.0 or value > 100.0:
                raise ForestControlError("Plant Group probability must be between 0 and 100.")
            group = self._selected_plant_group()
            if group is None or not group.manifest_backed:
                raise ForestControlError("Select a Plant Group before changing species probability.")
            return self._apply_group_runtime_live(group, "probability", value)
        except Exception as exc:
            self._state = replace(self._state, status="Plant Group probability edit rejected", error=f"{type(exc).__name__}: {exc}")
            return self._state

    def _selected_plant_group(self) -> PlantGroupTarget | None:
        group_id = self._state.selected_group_id
        if not group_id:
            return None
        return next((item for item in self._state.plant_groups if item.group_id == group_id), None)

    def _persist_group_artist_control(self, group: PlantGroupTarget, key: str, value: Any) -> ForestUIState:
        previous_manifest, manifest = self.scene_state.snapshot_and_working_copy(preflight=False)
        target = self.scene_state.group_payload(manifest, group.group_id)
        artist_values = target.get("artist_values")
        if not isinstance(artist_values, dict):
            artist_values = {}
            target["artist_values"] = artist_values
        artist_values[key] = value
        if key == "density_spacing":
            raw_spacing = self._display_distance_to_system(value, self._state.scene_units)
            target["spacing_system"] = [raw_spacing, raw_spacing]
        self.scene_state.write_verified(
            manifest,
            preflight=False,
            error_message="Plant-group artist setting write was not verified.",
        )
        if key == "density_spacing":
            try:
                execution = self.scene_runtime.execute_manifest(manifest)
                if execution.get("verified") is not True:
                    raise ForestControlError("Plant-group distribution execution was not verified.")
            except Exception:
                self.scene_state.restore_snapshot(previous_manifest, preflight=False)
                raise
        readback = self.scene_state.read_manifest(preflight=False)
        readback_groups = readback.get("groups") if isinstance(readback, dict) else None
        readback_target = next(
            (item for item in (readback_groups or []) if isinstance(item, dict) and str(item.get("group_id") or "") == group.group_id),
            None,
        )
        if readback_target is None:
            raise ForestControlError("Plant-group artist setting readback did not contain the selected group.")
        rb_values = readback_target.get("artist_values") if isinstance(readback_target.get("artist_values"), dict) else {}
        if rb_values.get(key) != value:
            raise ForestControlError("Plant-group artist setting readback mismatch.")
        state = self._load_forest(group.forest_name, preflight=False, selected_group_id=group.group_id)
        self._state = replace(
            state,
            status=f"{group.label}: {key.replace('_', ' ').title()} updated in 3ds Max" if key == "density_spacing" else f"{group.label}: {key.replace('_', ' ').title()} updated",
            error=None,
        )
        return self._state

    def set_artist_control(self, key: str, value: Any) -> ForestUIState:
        try:
            specs = {spec.key: spec for spec in artist_control_specs()}
            if key not in specs:
                raise ForestControlError(f"Unknown artist control: {key}")
            spec = specs[key]
            group = self._selected_plant_group()
            if group is None and self._state.selected_forest and self._state.plant_groups:
                # Forest 01 is a semantic parent, not a fourth planting layer.
                # Parent-level artist edits must fan out to all child Plant Groups
                # so the RGB diversity-map channels are regenerated together.
                if spec.kind == "choice":
                    token = str(value)
                    if token not in spec.options:
                        raise ForestControlError(f"Invalid artist control value for {spec.label}: {token}")
                    if key in {"naturalness", "cluster_character"}:
                        return self._stage_all_groups_artist_edit(key, token, "choice")
                    if key == "variation":
                        raise ForestControlError("Variation is not available until its Forest Pack activation flags are writable.")
                if key == "density_spacing":
                    try:
                        spacing = float(str(value).replace(",", "."))
                    except Exception as exc:
                        raise ForestControlError("Plant Spacing requires a positive numeric value.") from exc
                    if spacing <= 0.0:
                        raise ForestControlError("Plant Spacing must be greater than zero.")
                    return self._stage_all_groups_artist_edit(key, spacing, "float")
            if group is not None and group.manifest_backed:
                if spec.kind == "choice":
                    token = str(value)
                    if token not in spec.options:
                        raise ForestControlError(f"Invalid artist control value for {spec.label}: {token}")
                    if key == "variation":
                        raise ForestControlError("Variation is not available until its Forest Pack activation flags are writable.")
                    if key in {"naturalness", "cluster_character"}:
                        return self._stage_group_artist_edit(group, key, token, "choice")
                if key == "density_spacing":
                    try:
                        spacing = float(str(value).replace(",", "."))
                    except Exception as exc:
                        raise ForestControlError("Plant Spacing requires a positive numeric value.") from exc
                    if spacing <= 0.0:
                        raise ForestControlError("Plant Spacing must be greater than zero.")
                    return self._stage_group_artist_edit(group, key, spacing, "float")
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
                    artist_controls=self._artist_control_states(self._state.properties, self._state.scene_units, self._selected_plant_group()),
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
        runtime = self._state.selected_group_runtime
        group = self._selected_plant_group()
        if group is not None and group.manifest_backed:
            try:
                runtime = self._read_selected_group_runtime(group)
            except Exception:
                pass
        self._state = replace(
            self._state,
            pending_edits=(),
            selected_group_runtime=runtime,
            artist_controls=self._artist_control_states(self._state.properties, self._state.scene_units, group),
            status=f"Pending edits reverted for {self._state.selected_forest}" if self._state.selected_forest else "Pending edits reverted",
            error=None,
        )
        return self._state

    def reset_selected_target(self) -> ForestUIState:
        """Restore scene-persisted authored defaults and apply them to Max immediately."""
        try:
            forest_name = self._state.selected_forest
            if not forest_name:
                raise ForestControlError("No Forest selected.")
            manifest = self.scene_state.read_manifest(preflight=False)
            raw_groups = manifest.get("groups") if isinstance(manifest, dict) else None
            if not isinstance(raw_groups, list) or not raw_groups:
                raise ForestControlError("Plant-group manifest is missing or invalid.")

            if self._state.selected_group_id:
                target_ids = {self._state.selected_group_id}
            else:
                target_ids = {
                    group.group_id for group in self._state.plant_groups
                    if group.manifest_backed and group.forest_name == forest_name
                }
            if not target_ids:
                raise ForestControlError("No managed Plant Group is available to reset.")

            touched_ids: list[str] = []
            for item in raw_groups:
                if not isinstance(item, dict):
                    continue
                group_id = str(item.get("group_id") or "")
                if group_id not in target_ids:
                    continue
                defaults = self._canonical_group_reset_defaults(item)
                spacing = defaults.get("spacing_system")
                default_artist = defaults.get("artist_values")
                if not isinstance(spacing, (list, tuple)) or len(spacing) != 2 or not isinstance(default_artist, dict):
                    raise ForestControlError(f"Plant Group reset defaults are invalid: {group_id}")
                item["spacing_system"] = [float(spacing[0]), float(spacing[1])]
                artist_values = item.get("artist_values")
                if not isinstance(artist_values, dict):
                    artist_values = {}
                    item["artist_values"] = artist_values
                artist_values["species_enabled"] = bool(default_artist.get("species_enabled", True))
                artist_values["species_scale_percent"] = float(default_artist.get("species_scale_percent", 100.0))
                artist_values["naturalness"] = str(default_artist.get("naturalness") or "Balanced")
                artist_values["cluster_character"] = str(default_artist.get("cluster_character") or "Medium Clusters")
                artist_values.pop("density_spacing", None)
                touched_ids.append(group_id)

            if set(touched_ids) != set(target_ids):
                raise ForestControlError("One or more Plant Groups became stale before Reset.")
            self.scene_state.write_verified(
                manifest,
                preflight=False,
                error_message="Reset manifest write was not verified.",
            )

            # Reset is deliberately a full scene rebuild, not the interactive
            # fast path.  This forces ForestPack to re-evaluate the currently
            # edited Area spline, rebind the diversity map, restore the
            # authored grid/collision values, and rebuild the scatter even if
            # the spline geometry changed while Forest Manager was closed.
            distribution_result = self.scene_runtime.execute_manifest(manifest, strict_acceptance=False)
            if distribution_result.get("verified") is not True:
                raise ForestControlError("Reset scene rebuild was not verified.")

            current_groups = {group.group_id: group for group in self._state.plant_groups}
            for group_id in touched_ids:
                group = current_groups.get(group_id)
                if group is None:
                    raise ForestControlError(f"Plant Group became stale during Reset: {group_id}")
                target = next(
                    (item for item in raw_groups if isinstance(item, dict) and str(item.get("group_id") or "") == group_id),
                    None,
                )
                defaults = (target or {}).get("reset_defaults") if isinstance(target, dict) else {}
                default_artist = defaults.get("artist_values") if isinstance(defaults, dict) else {}
                species_ids: list[int] = []
                for index in self._group_geometry_indices(group):
                    value = int(self.service.get_array_element(group.forest_name, "specidlist", index, preflight=False).get("value") or 0)
                    if value > 0:
                        species_ids.append(value)
                if not species_ids:
                    raise ForestControlError(f"Plant Group species IDs could not be resolved during Reset: {group_id}")
                self.service.apply_plant_group_species_runtime(
                    group.forest_name,
                    species_ids,
                    enabled=bool((default_artist or {}).get("species_enabled", True)),
                    scale_percent=float((default_artist or {}).get("species_scale_percent", 100.0)),
                    preflight=False,
                )

            self._pending.clear()
            groups = discover_plant_groups(self._state.forest_names, manifest)
            selected_group = next((g for g in groups if g.group_id == self._state.selected_group_id), None)
            runtime = self._read_selected_group_runtime(selected_group) if selected_group is not None else None
            self._state = replace(
                self._state,
                plant_groups=groups,
                selected_group_label=selected_group.label if selected_group is not None else None,
                pending_edits=(),
                selected_group_runtime=runtime,
                artist_controls=self._artist_control_states(self._state.properties, self._state.scene_units, selected_group),
                status=(
                    f"Reset {selected_group.label} to scene-authored defaults"
                    if selected_group is not None
                    else "Reset Forest 01 Plant Groups to scene-authored defaults"
                ),
                error=None,
            )
            return self._state
        except Exception as exc:
            self._state = replace(self._state, status="Reset failed", error=f"{type(exc).__name__}: {exc}")
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

            group_edits = [edit for edit in self._pending.values() if edit.property_name.startswith("__plant_group__|")]
            forest_edits = [edit for edit in self._pending.values() if not edit.property_name.startswith("__plant_group__|")]
            applied_count = 0
            previous_manifest = None
            manifest = None
            if group_edits:
                previous_manifest, manifest = self.scene_state.snapshot_and_working_copy(preflight=False)
            raw_groups = manifest.get("groups") if isinstance(manifest, dict) else None
            if group_edits and not isinstance(raw_groups, list):
                raise ForestControlError("Plant-group manifest is missing or invalid.")

            applied_group_edits: list[tuple[PendingEdit, PlantGroupTarget]] = []
            try:
                for edit in group_edits:
                    _, group_id, field = edit.property_name.split("|", 2)
                    group = next((item for item in self._state.plant_groups if item.group_id == group_id), None)
                    if group is None or not group.manifest_backed:
                        raise ForestControlError(f"Plant Group became stale before Apply: {group_id}")
                    indices = self._group_geometry_indices(group)
                    if field not in {"enabled", "scale", "probability", "naturalness", "cluster_character", "density_spacing"}:
                        raise ForestControlError(f"Unsupported Plant Group pending field: {field}")

                    target = next(
                        (item for item in raw_groups if isinstance(item, dict) and str(item.get("group_id") or "") == group_id),
                        None,
                    )
                    if target is None:
                        raise ForestControlError(f"Plant group is missing from the scene manifest: {group_id}")
                    artist_values = target.get("artist_values")
                    if not isinstance(artist_values, dict):
                        artist_values = {}
                        target["artist_values"] = artist_values
                    if field == "enabled":
                        artist_values["species_enabled"] = bool(edit.value)
                    elif field == "scale":
                        artist_values["species_scale_percent"] = float(edit.value)
                    elif field == "probability":
                        artist_values["species_probability_percent"] = float(edit.value)
                    elif field in {"naturalness", "cluster_character"}:
                        artist_values[field] = edit.value
                    elif field == "density_spacing":
                        artist_values[field] = float(edit.value)
                        raw_spacing = self._display_distance_to_system(float(edit.value), self._state.scene_units)
                        target["spacing_system"] = [raw_spacing, raw_spacing]
                    applied_group_edits.append((edit, group))
                    applied_count += 1

                if group_edits:
                    self.scene_state.write_verified(
                        manifest,
                        preflight=False,
                        error_message="Plant-group pending settings were not persisted.",
                    )

                    # Only rebuild/rebind the Diversity Map for controls that
                    # actually change spatial distribution. Geometry-only
                    # controls such as Scale must not reset the map/viewport.
                    edited_fields = {edit.property_name.split("|", 2)[2] for edit in group_edits}
                    if "density_spacing" in edited_fields:
                        execution = refresh_plant_group_distribution_fast(manifest, service=self.service)
                        if execution.get("verified") is not True:
                            raise ForestControlError("Plant-group spacing Apply did not refresh the single-Forest distribution.")
                    elif edited_fields & {"enabled", "naturalness", "cluster_character"}:
                        execution = refresh_plant_group_diversity_map(manifest)
                        if execution.get("verified") is not True:
                            raise ForestControlError("Plant-group map Apply was not verified.")

                    # Geometry item edits use a single bridge transaction per group.
                    # This avoids repeated GET/SET/update/redraw cycles and forces a
                    # Custom Object cache rebind when Scale changes.
                    grouped: dict[str, dict[str, Any]] = {}
                    group_targets: dict[str, PlantGroupTarget] = {}
                    for edit in group_edits:
                        _, group_id, field = edit.property_name.split("|", 2)
                        group = next((item for item in self._state.plant_groups if item.group_id == group_id), None)
                        if group is None or not group.manifest_backed:
                            raise ForestControlError(f"Plant Group became stale during Apply: {group_id}")
                        group_targets[group_id] = group
                        bucket = grouped.setdefault(group_id, {})
                        if field == "enabled":
                            bucket["enabled"] = bool(edit.value)
                        elif field == "scale":
                            bucket["scale_percent"] = float(edit.value)
                        elif field == "probability":
                            bucket["probability_percent"] = float(edit.value)
                    for group_id, values in grouped.items():
                        group = group_targets[group_id]
                        target = next(
                            (item for item in raw_groups if isinstance(item, dict) and str(item.get("group_id") or "") == group_id),
                            None,
                        )
                        source_names = [str(value) for value in ((target or {}).get("source_names") or []) if str(value).strip()]
                        source_map = self._group_geometry_indices(group)
                        species_ids: list[int] = []
                        for index in source_map:
                            species_ids.append(int(self.service.get_array_element(group.forest_name, "specidlist", index, preflight=False).get("value") or 0))
                        species_ids = [value for value in species_ids if value > 0]
                        if not species_ids:
                            raise ForestControlError(f"Plant Group species IDs could not be resolved: {group_id}")
                        self.service.apply_plant_group_species_runtime(group.forest_name, species_ids, preflight=False, **values)

                if forest_edits:
                    operations = tuple(
                        UnifiedControlOperation(property_name=edit.property_name, value=edit.value, label="ui")
                        for edit in forest_edits
                    )
                    result = self.transaction_manager.execute(
                        operations, default_forest_name=forest_name, rollback_on_success=False
                    )
                    if not result.write_verified:
                        raise ForestControlError("UI transaction did not verify all writes.")
                    applied_count += result.operation_count
            except Exception:
                if previous_manifest is not None:
                    try:
                        self.scene_state.restore_snapshot(previous_manifest, preflight=False)
                    except Exception:
                        pass
                for edit, group in reversed(applied_group_edits):
                    try:
                        _, _, field = edit.property_name.split("|", 2)
                        for index in self._group_geometry_indices(group):
                            if field == "enabled":
                                self.service.set_array_element(group.forest_name, "geomlist", index, 2 if bool(edit.original_value) else 0, preflight=False)
                            elif field == "scale":
                                self.service.set_array_element(group.forest_name, "ScaleList", index, float(edit.original_value), preflight=False)
                            elif field == "probability":
                                self.service.set_array_element(group.forest_name, "problist", index, float(edit.original_value), preflight=False)
                            elif field in {"naturalness", "cluster_character", "density_spacing"}:
                                pass
                    except Exception:
                        pass
                raise

            self._pending.clear()
            # Rebuild the lightweight Plant Group targets from the manifest that
            # was just persisted.  Keeping the pre-Apply tuple here caused the UI
            # to repaint the old spacing (for example 75 m) immediately after a
            # successful 300 m Apply even though the scene manifest had changed.
            refreshed_groups = self._state.plant_groups
            if group_edits and isinstance(manifest, dict):
                try:
                    refreshed_groups = discover_plant_groups(forests, manifest)
                except Exception:
                    refreshed_groups = self._state.plant_groups
            selected_group_id = self._state.selected_group_id
            selected_group = next(
                (item for item in refreshed_groups if item.group_id == selected_group_id),
                None,
            ) if selected_group_id else None
            # Apply must not immediately perform another synchronous Max readback.
            # The just-persisted manifest is already the authoritative UI snapshot;
            # rebuild the lightweight runtime cache from it and keep the selection
            # stable.  Explicit Refresh Scene remains the path for scene readback.
            runtime = self._state.selected_group_runtime
            if group_edits and isinstance(manifest, dict):
                self._prime_group_runtime_cache(manifest, tuple(refreshed_groups))
            if selected_group is not None and selected_group.manifest_backed:
                cached_runtime = dict(self._group_runtime_cache.get(selected_group.group_id) or {})
                if cached_runtime:
                    runtime = cached_runtime
            self._state = replace(
                self._state,
                plant_groups=tuple(refreshed_groups),
                pending_edits=(),
                selected_group_runtime=runtime,
                artist_controls=self._artist_control_states(self._state.properties, self._state.scene_units, selected_group),
                status=f"Applied {applied_count} change(s) to {forest_name}",
                error=None,
            )
            return self._state
        except Exception as exc:
            self._state = replace(self._state, status="Apply failed", error=f"{type(exc).__name__}: {exc}")
            return self._state
