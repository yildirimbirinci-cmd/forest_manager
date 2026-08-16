from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .semantic_transaction import UnifiedControlOperation, UnifiedControlTransactionManager, UnifiedTransactionResult
from .service import ForestControlError, ForestPackControlService


@dataclass(frozen=True)
class AreaBoundaryRecord:
    index: int
    area_id: Any
    active: Any
    name: str
    node_name: str
    area_type: Any
    include_exclude: Any
    width: Any
    threshold: Any
    density_falloff: Any
    scale_falloff: Any
    boundary_check: Any
    project_mode: Any
    obstacle_scale: Any
    scale_min: Any
    scale_max: Any
    z_offset: Any


@dataclass(frozen=True)
class AreaBoundaryUpdate:
    width: float | None = None
    threshold: float | None = None
    density_falloff: float | None = None
    scale_falloff: float | None = None
    boundary_check: int | None = None
    project_mode: int | None = None
    obstacle_scale: float | None = None
    scale_min: float | None = None
    scale_max: float | None = None
    z_offset: float | None = None


class AreaBoundaryRecordAdapter:
    """Atomic adapter over Forest Pack's synchronized AreaParameter arrays.

    The adapter treats one array index as a logical Area record, validates that
    the synchronized arrays remain aligned, and delegates writes to the verified
    unified transaction layer so partial failures roll back the record patch.
    """

    IDENTITY_PROPERTIES = (
        "aridlist",
        "pf_aractivelist",
        "arnamelist",
        "arnodenamelist",
        "artypelist",
        "arincexclist",
    )
    MUTABLE_PROPERTIES = {
        "width": "arwidthlist",
        "threshold": "arthresholdlist",
        "density_falloff": "arflafdenslist",
        "scale_falloff": "arflafscalist",
        "boundary_check": "arboundchecklist",
        "project_mode": "arprojectlist",
        "obstacle_scale": "arobscalelist",
        "scale_min": "arscalemin",
        "scale_max": "arscalemax",
        "z_offset": "arzoffset",
    }
    RECORD_PROPERTIES = IDENTITY_PROPERTIES + tuple(MUTABLE_PROPERTIES.values())

    def __init__(
        self,
        service: ForestPackControlService | None = None,
        transaction: UnifiedControlTransactionManager | None = None,
    ) -> None:
        self.service = service or ForestPackControlService()
        self.transaction = transaction or UnifiedControlTransactionManager(self.service)

    def _array_count(self, forest_name: str, property_name: str, *, preflight: bool) -> int:
        prop = self.service.get_property(forest_name, property_name, preflight=preflight)
        metadata = prop.get("array") or prop.get("array_metadata")
        if not isinstance(metadata, dict):
            raise ForestControlError(f"Area record property is not an array: {forest_name}.{property_name}")
        try:
            count = int(metadata.get("count"))
        except (TypeError, ValueError) as exc:
            raise ForestControlError(f"Area record property has invalid array count: {property_name}") from exc
        if count < 0:
            raise ForestControlError(f"Area record property has negative array count: {property_name}")
        return count

    def validate_alignment(self, forest_name: str) -> int:
        counts: dict[str, int] = {}
        for position, property_name in enumerate(self.RECORD_PROPERTIES):
            counts[property_name] = self._array_count(forest_name, property_name, preflight=(position == 0))
        unique = set(counts.values())
        if len(unique) != 1:
            detail = ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
            raise ForestControlError(f"Forest Area arrays are not synchronized: {detail}")
        return next(iter(unique), 0)

    def _read_value(self, forest_name: str, property_name: str, index: int, *, preflight: bool = False) -> Any:
        return self.service.get_array_element(forest_name, property_name, index, preflight=preflight).get("value")

    def read_record(self, forest_name: str, index: int, *, validate_alignment: bool = True) -> AreaBoundaryRecord:
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise ForestControlError("Area record index must be a non-negative integer.")
        count = self.validate_alignment(forest_name) if validate_alignment else self._array_count(
            forest_name, "aridlist", preflight=True
        )
        if index >= count:
            raise ForestControlError(f"Area record index is outside the synchronized arrays: {index}/{count}")
        values: dict[str, Any] = {}
        for property_name in self.RECORD_PROPERTIES:
            values[property_name] = self._read_value(forest_name, property_name, index)
        name = str(values.get("arnamelist") or "").strip()
        node_name = str(values.get("arnodenamelist") or "").strip()
        return AreaBoundaryRecord(
            index=index,
            area_id=values.get("aridlist"),
            active=values.get("pf_aractivelist"),
            name=name,
            node_name=node_name,
            area_type=values.get("artypelist"),
            include_exclude=values.get("arincexclist"),
            width=values.get("arwidthlist"),
            threshold=values.get("arthresholdlist"),
            density_falloff=values.get("arflafdenslist"),
            scale_falloff=values.get("arflafscalist"),
            boundary_check=values.get("arboundchecklist"),
            project_mode=values.get("arprojectlist"),
            obstacle_scale=values.get("arobscalelist"),
            scale_min=values.get("arscalemin"),
            scale_max=values.get("arscalemax"),
            z_offset=values.get("arzoffset"),
        )

    def list_records(self, forest_name: str) -> tuple[AreaBoundaryRecord, ...]:
        count = self.validate_alignment(forest_name)
        return tuple(self.read_record(forest_name, index, validate_alignment=False) for index in range(count))

    @staticmethod
    def _update_items(update: AreaBoundaryUpdate) -> Iterable[tuple[str, Any]]:
        for field_name in AreaBoundaryRecordAdapter.MUTABLE_PROPERTIES:
            value = getattr(update, field_name)
            if value is not None:
                yield field_name, value

    def build_update_operations(
        self,
        forest_name: str,
        index: int,
        update: AreaBoundaryUpdate,
    ) -> tuple[UnifiedControlOperation, ...]:
        record = self.read_record(forest_name, index)
        items = tuple(self._update_items(update))
        if not items:
            raise ForestControlError("Area boundary update requires at least one changed field.")
        operations: list[UnifiedControlOperation] = []
        for field_name, value in items:
            property_name = self.MUTABLE_PROPERTIES[field_name]
            operations.append(
                UnifiedControlOperation(
                    forest_name=forest_name,
                    property_name=property_name,
                    index=index,
                    value=value,
                    label=f"area_record[{record.index}].{field_name}",
                )
            )
        self.transaction.validate_operations(operations)
        return tuple(operations)

    def apply_update(
        self,
        forest_name: str,
        index: int,
        update: AreaBoundaryUpdate,
        *,
        rollback_on_success: bool = False,
    ) -> UnifiedTransactionResult:
        before_count = self.validate_alignment(forest_name)
        operations = self.build_update_operations(forest_name, index, update)
        result = self.transaction.execute(operations, rollback_on_success=rollback_on_success)
        after_count = self.validate_alignment(forest_name)
        if before_count != after_count:
            raise ForestControlError(
                f"Area record count changed across atomic update: {before_count} -> {after_count}"
            )
        return result
