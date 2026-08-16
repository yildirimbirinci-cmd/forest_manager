from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Iterable, Mapping

from forest_manager.forest_control.area_records import AreaBoundaryRecordAdapter, AreaBoundaryUpdate
from forest_manager.forest_control.semantic_transaction import UnifiedControlOperation, UnifiedControlTransactionManager, UnifiedTransactionResult
from forest_manager.forest_control.service import ForestControlError, ForestPackControlService

from .planting_planning import PlantingDirective, PlantingIntentKind, PlantingPlan
from .schema import SiteGeometry
from .service import SiteModelService


class ExecutionBlockReason(str, Enum):
    MISSING_FOREST_BINDING = "missing_forest_binding"
    SPECIES_SOURCE_ASSIGNMENT_UNAVAILABLE = "species_source_assignment_unavailable"
    KEEP_CLEAR_AREA_MODE_UNAVAILABLE = "keep_clear_area_mode_unavailable"
    INVALID_EXECUTION_METADATA = "invalid_execution_metadata"
    NO_EXECUTABLE_MAPPING = "no_executable_mapping"


@dataclass(frozen=True)
class BlockedPlantingDirective:
    geometry_id: str
    intent: PlantingIntentKind
    reason: ExecutionBlockReason
    detail: str


@dataclass(frozen=True)
class ForestPackExecutionPlan:
    revision: int
    operations: tuple[UnifiedControlOperation, ...]
    blocked: tuple[BlockedPlantingDirective, ...]

    @property
    def executable_operation_count(self) -> int:
        return len(self.operations)

    @property
    def blocked_directive_count(self) -> int:
        return len(self.blocked)

    @property
    def fully_executable(self) -> bool:
        return bool(self.operations) and not self.blocked


@dataclass(frozen=True)
class ForestPackExecutionResult:
    plan: ForestPackExecutionPlan
    transaction: UnifiedTransactionResult | None
    partial: bool


_AREA_FIELD_MAP: Mapping[str, str] = {
    "forest_area_width": "width",
    "forest_area_threshold": "threshold",
    "forest_density_falloff": "density_falloff",
    "forest_scale_falloff": "scale_falloff",
    "forest_boundary_check": "boundary_check",
    "forest_project_mode": "project_mode",
    "forest_obstacle_scale": "obstacle_scale",
    "forest_scale_min": "scale_min",
    "forest_scale_max": "scale_max",
    "forest_z_offset": "z_offset",
}

_DISTRIBUTION_SCALARS: Mapping[str, str] = {
    "forest_distribution_density_units_x": "units_x",
    "forest_distribution_density_units_y": "units_y",
    "forest_cluster_size": "clusize",
    "forest_cluster_roughness": "clurough",
    "forest_cluster_noise": "clunoise",
    "forest_cluster_edge": "cluedge",
}


class ForestPackPlantingExecutionBridge:
    """Translate a resolved PlantingPlan into verified Forest Pack write operations.

    The bridge is intentionally capability-gated. It only emits operations for endpoints
    already verified by the Forest Pack control layer. It never invents geometry-source
    insertion, Area include/exclude switching, or implicit density conversions.
    """

    def __init__(
        self,
        service: ForestPackControlService | None = None,
        transaction: UnifiedControlTransactionManager | None = None,
        area_adapter: AreaBoundaryRecordAdapter | None = None,
    ) -> None:
        self.service = service or ForestPackControlService()
        self.transaction = transaction or UnifiedControlTransactionManager(self.service)
        self.area_adapter = area_adapter or AreaBoundaryRecordAdapter(self.service, self.transaction)

    def build_execution_plan(
        self,
        site_service: SiteModelService,
        planting_plan: PlantingPlan,
        *,
        default_forest_name: str | None = None,
    ) -> ForestPackExecutionPlan:
        geometries = {item.geometry_id: item for item in site_service.snapshot().geometries}
        operations: list[UnifiedControlOperation] = []
        blocked: list[BlockedPlantingDirective] = []
        seen_targets: dict[tuple[str, str, int | None], Any] = {}

        for directive in planting_plan.directives:
            geometry = geometries.get(directive.geometry_id)
            if geometry is None:
                blocked.append(BlockedPlantingDirective(
                    directive.geometry_id,
                    directive.intent,
                    ExecutionBlockReason.INVALID_EXECUTION_METADATA,
                    "Planting directive references missing Site Model geometry.",
                ))
                continue
            forest_name = self._forest_name(geometry, default_forest_name)
            if not forest_name:
                blocked.append(BlockedPlantingDirective(
                    directive.geometry_id,
                    directive.intent,
                    ExecutionBlockReason.MISSING_FOREST_BINDING,
                    "Set geometry metadata 'forest_name' or provide default_forest_name.",
                ))
                continue

            directive_ops, directive_blocks = self._compile_directive(forest_name, geometry, directive)
            blocked.extend(directive_blocks)
            for operation in directive_ops:
                key = (str(operation.forest_name or forest_name), operation.property_name, operation.index)
                if key in seen_targets and seen_targets[key] != operation.value:
                    blocked.append(BlockedPlantingDirective(
                        directive.geometry_id,
                        directive.intent,
                        ExecutionBlockReason.INVALID_EXECUTION_METADATA,
                        f"Conflicting Forest Pack target {key[0]}.{key[1]} for multiple planting directives.",
                    ))
                    continue
                if key not in seen_targets:
                    seen_targets[key] = operation.value
                    operations.append(operation)

        return ForestPackExecutionPlan(
            revision=planting_plan.revision,
            operations=tuple(operations),
            blocked=tuple(blocked),
        )

    def execute(
        self,
        plan: ForestPackExecutionPlan,
        *,
        allow_partial: bool = False,
        rollback_on_success: bool = False,
    ) -> ForestPackExecutionResult:
        if plan.blocked and not allow_partial:
            detail = "; ".join(f"{item.geometry_id}:{item.reason.value}" for item in plan.blocked)
            raise ForestControlError(f"Planting execution plan contains blocked directives: {detail}")
        if not plan.operations:
            raise ForestControlError("Planting execution plan has no verified writable Forest Pack operations.")
        result = self.transaction.execute(plan.operations, rollback_on_success=rollback_on_success)
        return ForestPackExecutionResult(plan=plan, transaction=result, partial=bool(plan.blocked))

    def _compile_directive(
        self,
        forest_name: str,
        geometry: SiteGeometry,
        directive: PlantingDirective,
    ) -> tuple[list[UnifiedControlOperation], list[BlockedPlantingDirective]]:
        metadata = geometry.metadata
        operations: list[UnifiedControlOperation] = []
        blocked: list[BlockedPlantingDirective] = []

        area_index = self._optional_non_negative_int(metadata.get("forest_area_index"), "forest_area_index")
        area_update = self._area_update(metadata)
        if area_index is not None and area_update is not None:
            operations.extend(self._area_operations(forest_name, area_index, area_update, directive.geometry_id))

        density = metadata.get("forest_distribution_density_units")
        if density is not None:
            numeric = self._finite_number(density, "forest_distribution_density_units")
            operations.extend((
                UnifiedControlOperation(forest_name=forest_name, property_name="units_x", value=numeric, label=f"{directive.geometry_id}.density_x"),
                UnifiedControlOperation(forest_name=forest_name, property_name="units_y", value=numeric, label=f"{directive.geometry_id}.density_y"),
            ))

        for metadata_key, property_name in _DISTRIBUTION_SCALARS.items():
            if metadata_key not in metadata:
                continue
            numeric = self._finite_number(metadata[metadata_key], metadata_key)
            operations.append(UnifiedControlOperation(
                forest_name=forest_name,
                property_name=property_name,
                value=numeric,
                label=f"{directive.geometry_id}.{property_name}",
            ))

        if directive.intent is PlantingIntentKind.SPECIES and directive.species:
            blocked.append(BlockedPlantingDirective(
                directive.geometry_id,
                directive.intent,
                ExecutionBlockReason.SPECIES_SOURCE_ASSIGNMENT_UNAVAILABLE,
                "Species metadata is preserved, but the verified Forest Pack bridge has no safe geometry-source insertion contract.",
            ))

        if directive.intent is PlantingIntentKind.EXCLUSION:
            blocked.append(BlockedPlantingDirective(
                directive.geometry_id,
                directive.intent,
                ExecutionBlockReason.KEEP_CLEAR_AREA_MODE_UNAVAILABLE,
                "KEEP_CLEAR requires atomic Area include/exclude creation or mode switching, which is not exposed by the verified bridge.",
            ))

        if not operations and not blocked:
            blocked.append(BlockedPlantingDirective(
                directive.geometry_id,
                directive.intent,
                ExecutionBlockReason.NO_EXECUTABLE_MAPPING,
                "No explicit Forest Pack execution metadata was provided for this planting directive.",
            ))
        return operations, blocked

    def _area_operations(
        self,
        forest_name: str,
        index: int,
        update: AreaBoundaryUpdate,
        geometry_id: str,
    ) -> tuple[UnifiedControlOperation, ...]:
        values = {
            field_name: getattr(update, field_name)
            for field_name in AreaBoundaryRecordAdapter.MUTABLE_PROPERTIES
            if getattr(update, field_name) is not None
        }
        return tuple(
            UnifiedControlOperation(
                forest_name=forest_name,
                property_name=AreaBoundaryRecordAdapter.MUTABLE_PROPERTIES[field_name],
                index=index,
                value=value,
                label=f"{geometry_id}.area[{index}].{field_name}",
            )
            for field_name, value in values.items()
        )

    @staticmethod
    def _forest_name(geometry: SiteGeometry, default_forest_name: str | None) -> str:
        value = geometry.metadata.get("forest_name")
        if value is None or not str(value).strip():
            value = default_forest_name
        return str(value or "").strip()

    @classmethod
    def _area_update(cls, metadata: Mapping[str, Any]) -> AreaBoundaryUpdate | None:
        kwargs: dict[str, Any] = {}
        for metadata_key, field_name in _AREA_FIELD_MAP.items():
            if metadata_key not in metadata:
                continue
            raw = metadata[metadata_key]
            if field_name in {"boundary_check", "project_mode"}:
                if isinstance(raw, bool) or not isinstance(raw, int):
                    raise ForestControlError(f"{metadata_key} must be an integer.")
                kwargs[field_name] = raw
            else:
                kwargs[field_name] = cls._finite_number(raw, metadata_key)
        return AreaBoundaryUpdate(**kwargs) if kwargs else None

    @staticmethod
    def _optional_non_negative_int(value: Any, name: str) -> int | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ForestControlError(f"{name} must be a non-negative integer.")
        return value

    @staticmethod
    def _finite_number(value: Any, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ForestControlError(f"{name} must be numeric.")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ForestControlError(f"{name} must be finite.")
        return numeric


__all__ = [
    "BlockedPlantingDirective",
    "ExecutionBlockReason",
    "ForestPackExecutionPlan",
    "ForestPackExecutionResult",
    "ForestPackPlantingExecutionBridge",
]
