from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from forest_manager.max_bridge.runtime_bridge import (
    delete_managed_forest,
    managed_scene_status,
    protect_managed_scene,
    read_plant_group_manifest,
    write_plant_group_manifest,
)

from .area_records import AreaBoundaryRecordAdapter, AreaBoundaryUpdate
from .geometry import GeometrySourcesAdapter
from .service import ForestControlError, ForestPackControlService

PRIMARY_FOREST = "FM_Forest_001"
LEGACY_PREFIX = "FM_Layer_"


@dataclass(frozen=True)
class PlantGroupMigrationRecord:
    group_id: str
    label: str
    order: int
    legacy_forest_name: str
    source_names: tuple[str, ...]
    spacing_system: tuple[float, float]
    area_nodes: tuple[str, ...]
    area_modes: tuple[int, ...]


@dataclass(frozen=True)
class PlantGroupMigrationPlan:
    primary_forest: str
    groups: tuple[PlantGroupMigrationRecord, ...]
    primary_source_names: tuple[str, ...]
    technical_forests: tuple[str, ...]
    representational_warning: str | None

    def manifest(self) -> dict[str, Any]:
        groups: list[dict[str, Any]] = []
        for group in self.groups:
            item = asdict(group)
            item["source_names"] = list(group.source_names)
            item["spacing_system"] = list(group.spacing_system)
            item["area_nodes"] = list(group.area_nodes)
            item["area_modes"] = list(group.area_modes)
            groups.append(item)
        return {
            "schema_version": 1,
            "primary_forest": self.primary_forest,
            "migration": "legacy_runtime_forests_to_semantic_plant_groups",
            "groups": groups,
            "representational_warning": self.representational_warning,
        }


def _inventory_property(service: ForestPackControlService, forest_name: str, property_name: str) -> Any:
    inventory = service.inventory(forest_name, preflight=False)
    for prop in inventory.get("properties") or ():
        if isinstance(prop, dict) and str(prop.get("name") or "").lower() == property_name.lower():
            return prop.get("value")
    raise ForestControlError(f"Forest property not found during migration: {forest_name}.{property_name}")


def _geometry_count(service: ForestPackControlService, forest_name: str) -> int:
    inventory = service.inventory(forest_name, preflight=False)
    for prop in inventory.get("properties") or ():
        if isinstance(prop, dict) and str(prop.get("name") or "").lower() == "cobjlist":
            meta = prop.get("array_metadata")
            if isinstance(meta, dict):
                return int(meta.get("count") or 0)
    return 0


def _humanize_legacy_name(name: str) -> tuple[int, str]:
    suffix = name[len(LEGACY_PREFIX):]
    parts = suffix.split("_", 1)
    try:
        order = int(parts[0])
    except (TypeError, ValueError):
        order = 9999
    label = (parts[1] if len(parts) > 1 else f"Plant Group {order}").replace("_", " ").strip().title()
    return order, label


def build_legacy_plant_group_plan(
    service: ForestPackControlService | None = None,
) -> PlantGroupMigrationPlan:
    service = service or ForestPackControlService()
    forests = tuple(service.list_forests(preflight=True))
    if PRIMARY_FOREST not in forests:
        raise ForestControlError(f"Primary managed Forest is missing: {PRIMARY_FOREST}")
    technical = tuple(sorted((name for name in forests if name.startswith(LEGACY_PREFIX)), key=str.lower))
    geometry = GeometrySourcesAdapter(service)
    areas = AreaBoundaryRecordAdapter(service)

    primary_sources = tuple(
        geometry.read_record(PRIMARY_FOREST, index).source_node or geometry.read_record(PRIMARY_FOREST, index).name
        for index in range(1, _geometry_count(service, PRIMARY_FOREST) + 1)
    )
    primary_source_set = {name for name in primary_sources if name}

    groups: list[PlantGroupMigrationRecord] = []
    spacing_values: set[tuple[float, float]] = set()
    for forest_name in technical:
        order, label = _humanize_legacy_name(forest_name)
        count = _geometry_count(service, forest_name)
        source_names = tuple(
            geometry.read_record(forest_name, index).source_node or geometry.read_record(forest_name, index).name
            for index in range(1, count + 1)
        )
        missing = [name for name in source_names if name and name not in primary_source_set]
        if missing:
            raise ForestControlError(
                f"Cannot consolidate {forest_name}; primary Forest is missing geometry sources: {', '.join(missing)}"
            )
        spacing = (
            float(_inventory_property(service, forest_name, "units_x")),
            float(_inventory_property(service, forest_name, "units_y")),
        )
        spacing_values.add(spacing)
        active_areas = tuple(record for record in areas.list_records(forest_name) if bool(record.active) and record.node_name)
        groups.append(
            PlantGroupMigrationRecord(
                group_id=f"plant_group:{order}:{forest_name}",
                label=label,
                order=order,
                legacy_forest_name=forest_name,
                source_names=tuple(name for name in source_names if name),
                spacing_system=spacing,
                area_nodes=tuple(record.node_name for record in active_areas),
                area_modes=tuple(int(record.include_exclude) for record in active_areas),
            )
        )

    warning = None
    if len(spacing_values) > 1:
        warning = (
            "Legacy plant groups use different Forest-object spacing values. The values are preserved in the "
            "scene plant-group manifest, but Forest Pack exposes units_x/units_y at Forest-object scope, so the "
            "single runtime Forest cannot reproduce all group spacing values simultaneously without a later "
            "group-distribution execution layer."
        )
    return PlantGroupMigrationPlan(
        primary_forest=PRIMARY_FOREST,
        groups=tuple(sorted(groups, key=lambda item: (item.order, item.legacy_forest_name.lower()))),
        primary_source_names=primary_sources,
        technical_forests=technical,
        representational_warning=warning,
    )


def _normalize_primary_area_contract(
    plan: PlantGroupMigrationPlan,
    service: ForestPackControlService,
) -> tuple[dict[str, Any], ...]:
    if not plan.groups:
        return ()
    include_nodes: set[str] = set()
    for group in plan.groups:
        for node_name, mode in zip(group.area_nodes, group.area_modes):
            if mode == 0:
                include_nodes.add(node_name)
    if not include_nodes:
        return ()
    adapter = AreaBoundaryRecordAdapter(service)
    changed: list[dict[str, Any]] = []
    for record in adapter.list_records(plan.primary_forest):
        if not bool(record.active) or record.node_name not in include_nodes or int(record.include_exclude) == 0:
            continue
        adapter.apply_update(
            plan.primary_forest,
            record.index,
            AreaBoundaryUpdate(include_exclude=0),
        )
        readback = adapter.read_record(plan.primary_forest, record.index)
        if int(readback.include_exclude) != 0:
            raise ForestControlError(
                f"Primary area normalization did not verify: {plan.primary_forest}[{record.index}]"
            )
        changed.append({"index": record.index, "node_name": record.node_name, "before": int(record.include_exclude), "after": 0})
    return tuple(changed)


def apply_legacy_plant_group_consolidation(
    service: ForestPackControlService | None = None,
    *,
    allow_spacing_semantic_only: bool = False,
) -> dict[str, Any]:
    service = service or ForestPackControlService()
    plan = build_legacy_plant_group_plan(service)
    if not plan.technical_forests:
        existing = read_plant_group_manifest()
        return {
            "changed": False,
            "primary_forest": plan.primary_forest,
            "technical_forests_removed": [],
            "manifest": existing,
            "verified": True,
        }
    if plan.representational_warning and not allow_spacing_semantic_only:
        raise ForestControlError(
            plan.representational_warning
            + " Re-run with allow_spacing_semantic_only=True only after accepting this known Forest Pack limitation."
        )

    status = managed_scene_status()
    managed = set(status.get("managed_forests") or ())
    missing_ownership = [name for name in plan.technical_forests if name not in managed]
    if missing_ownership:
        raise ForestControlError(
            "Refusing destructive consolidation because legacy Forest ownership is not verified: "
            + ", ".join(missing_ownership)
        )

    manifest = plan.manifest()
    write_result = write_plant_group_manifest(manifest)
    if write_result.get("verified") is not True:
        raise ForestControlError("Plant-group manifest write was not verified before consolidation.")
    readback_manifest = read_plant_group_manifest()
    if readback_manifest != manifest:
        raise ForestControlError("Plant-group manifest readback mismatch; legacy Forests were not deleted.")

    area_changes = _normalize_primary_area_contract(plan, service)
    removed: list[str] = []
    for name in plan.technical_forests:
        result = delete_managed_forest(name)
        if result.get("verified") is not True or (not result.get("deleted") and not result.get("missing")):
            raise ForestControlError(f"Legacy managed Forest deletion was not verified: {name}")
        removed.append(name)

    protect_managed_scene()
    remaining = tuple(service.list_forests(preflight=False))
    leftovers = [name for name in plan.technical_forests if name in remaining]
    if leftovers:
        raise ForestControlError("Legacy Forest consolidation verification failed: " + ", ".join(leftovers))
    if plan.primary_forest not in remaining:
        raise ForestControlError("Primary Forest disappeared during consolidation.")

    return {
        "changed": True,
        "primary_forest": plan.primary_forest,
        "technical_forests_removed": removed,
        "area_changes": list(area_changes),
        "manifest": readback_manifest,
        "representational_warning": plan.representational_warning,
        "verified": True,
    }
