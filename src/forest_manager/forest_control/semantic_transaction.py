from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:
    from .semantic_api import SemanticForestControlAPI
from .service import ForestControlError, ForestPackControlService


@dataclass(frozen=True)
class SemanticScalarChange:
    domain: str
    control: str
    raw_property: str
    value: bool | int | float | str


@dataclass(frozen=True)
class SemanticTransactionResult:
    forest_name: str
    operation_count: int
    blocked_operation_count: int
    rollback_step_count: int
    write_verified: bool
    rollback_verified: bool
    before_snapshot: dict[str, Any]
    after_write_snapshot: dict[str, Any]
    after_rollback_snapshot: dict[str, Any]
    runtime_write_endpoint: bool
    runtime_rollback_endpoint: bool


@dataclass(frozen=True)
class UnifiedControlOperation:
    property_name: str
    value: Any
    forest_name: str | None = None
    index: int | None = None
    label: str = ""


@dataclass(frozen=True)
class UnifiedTransactionResult:
    default_forest_name: str | None
    operation_count: int
    blocked_operation_count: int
    rollback_step_count: int
    write_verified: bool
    rollback_verified: bool
    automatic_rollback: bool
    rolled_back_on_success: bool
    before_snapshot: dict[str, Any]
    after_write_snapshot: dict[str, Any]
    after_rollback_snapshot: dict[str, Any]
    operations: tuple[dict[str, Any], ...]


class UnifiedControlTransactionManager:
    """Production transaction boundary over verified ForestPackControlService endpoints."""

    def __init__(self, service: ForestPackControlService | None = None) -> None:
        self.service = service or ForestPackControlService()

    @staticmethod
    def _target_key(forest_name: str, property_name: str, index: int | None) -> str:
        return f"{forest_name}.{property_name}" if index is None else f"{forest_name}.{property_name}[{index}]"

    @staticmethod
    def _resolve_forest(operation: UnifiedControlOperation, default_forest_name: str | None) -> str:
        forest_name = operation.forest_name or default_forest_name
        if not isinstance(forest_name, str) or not forest_name.strip():
            raise ForestControlError(
                f"Unified transaction operation requires an explicit or default Forest target: {operation.property_name}"
            )
        return forest_name.strip()

    @staticmethod
    def _same(actual: Any, expected: Any) -> bool:
        if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
            if len(actual) != len(expected):
                return False
            return all(UnifiedControlTransactionManager._same(a, b) for a, b in zip(actual, expected))
        if isinstance(actual, bool) or isinstance(expected, bool):
            return actual is expected
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            return abs(float(actual) - float(expected)) <= 1e-5
        return actual == expected

    def _read(self, forest_name: str, property_name: str, index: int | None, *, preflight: bool) -> dict[str, Any]:
        if index is not None:
            return self.service.get_array_element(forest_name, property_name, index, preflight=preflight)
        if property_name.lower() in self.service.TEXTURE_REFERENCE_PROPERTIES:
            return self.service.get_texture_reference(forest_name, property_name, preflight=preflight)
        return self.service.get_property(forest_name, property_name, preflight=preflight)

    def _validate(self, operation: UnifiedControlOperation, default_forest_name: str | None, *, preflight: bool) -> dict[str, Any]:
        forest_name = self._resolve_forest(operation, default_forest_name)
        property_name = operation.property_name.strip() if isinstance(operation.property_name, str) else ""
        if not property_name:
            raise ForestControlError("Unified transaction property name must be non-empty.")
        index = operation.index
        if index is not None and (isinstance(index, bool) or not isinstance(index, int) or index < 0):
            raise ForestControlError(f"Unified transaction array index must be a non-negative integer: {index}")

        before = self._read(forest_name, property_name, index, preflight=preflight)
        value_class = str(before.get("value_class") or "")
        reference_type = str(before.get("reference_type") or "")
        if index is None:
            if property_name.lower() in self.service.TEXTURE_REFERENCE_PROPERTIES:
                expected = self.service._normalize_texture_reference(operation.value)
                write_mode = "texture_ref"
            else:
                write_mode = str(before.get("write_mode") or "")
                if write_mode == "scalar":
                    self.service._scalar_type_for(value_class, operation.value)
                    expected = operation.value
                elif write_mode == "color" and value_class == "Color":
                    expected = list(self.service._normalize_color(operation.value))
                else:
                    raise ForestControlError(
                        f"Unified transaction property is not writable: {forest_name}.{property_name} "
                        f"class={value_class} mode={write_mode}"
                    )
        else:
            if reference_type == "node" and property_name.lower() in self.service.NODE_REFERENCE_ARRAY_PROPERTIES:
                expected = self.service._normalize_node_reference(operation.value)
                write_mode = "array_node_ref"
            elif reference_type == "material" and property_name.lower() in self.service.MATERIAL_REFERENCE_ARRAY_PROPERTIES:
                expected = self.service._normalize_material_reference(operation.value)
                write_mode = "array_material_ref"
            elif reference_type == "cproxy" and property_name.lower() in self.service.CPROXY_REFERENCE_ARRAY_PROPERTIES:
                expected = self.service._normalize_cproxy_reference(operation.value)
                write_mode = "array_cproxy_ref"
            elif value_class == "Point3":
                expected = list(self.service._normalize_point3(operation.value))
                write_mode = "array_point3"
            else:
                self.service._scalar_type_for(value_class, operation.value)
                expected = operation.value
                write_mode = "array_scalar"

        return {
            "forest_name": forest_name,
            "property_name": property_name,
            "index": index,
            "label": operation.label,
            "write_mode": write_mode,
            "value_class": value_class,
            "before": before.get("value"),
            "expected": expected,
        }

    def validate_operations(
        self,
        operations: Iterable[UnifiedControlOperation],
        *,
        default_forest_name: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        raw = tuple(operations)
        if not raw:
            raise ForestControlError("Unified transaction requires at least one operation.")
        validated: list[dict[str, Any]] = []
        seen: set[str] = set()
        for position, operation in enumerate(raw):
            if not isinstance(operation, UnifiedControlOperation):
                raise ForestControlError(f"Unified transaction operation {position} has an invalid type.")
            item = self._validate(operation, default_forest_name, preflight=(position == 0))
            key = self._target_key(item["forest_name"], item["property_name"], item["index"])
            if key in seen:
                raise ForestControlError(f"Duplicate unified transaction target: {key}")
            seen.add(key)
            validated.append(item)
        return tuple(validated)

    def _snapshot(self, validated: Iterable[dict[str, Any]]) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        for position, item in enumerate(validated):
            key = self._target_key(item["forest_name"], item["property_name"], item["index"])
            payload = self._read(item["forest_name"], item["property_name"], item["index"], preflight=(position == 0))
            snapshot[key] = payload.get("value")
        return snapshot

    def execute(
        self,
        operations: Iterable[UnifiedControlOperation],
        *,
        default_forest_name: str | None = None,
        rollback_on_success: bool = False,
    ) -> UnifiedTransactionResult:
        validated = self.validate_operations(operations, default_forest_name=default_forest_name)
        before = {self._target_key(i["forest_name"], i["property_name"], i["index"]): i["before"] for i in validated}
        marker = self.service.rollback_marker()
        operation_results: list[dict[str, Any]] = []
        after_write: dict[str, Any] = {}
        rollback_results: list[dict[str, Any]] = []
        automatic_rollback = False
        try:
            for item in validated:
                if item["index"] is None:
                    result = self.service.set_property(item["forest_name"], item["property_name"], item["expected"], preflight=False)
                else:
                    result = self.service.set_array_element(
                        item["forest_name"], item["property_name"], int(item["index"]), item["expected"], preflight=False
                    )
                operation_results.append({
                    "forest_name": item["forest_name"],
                    "property_name": item["property_name"],
                    "index": item["index"],
                    "write_mode": item["write_mode"],
                    "verified": bool(result.get("verified")),
                })

            after_write = self._snapshot(validated)
            for item in validated:
                key = self._target_key(item["forest_name"], item["property_name"], item["index"])
                if not self._same(after_write.get(key), item["expected"]):
                    raise ForestControlError(f"Unified transaction write verification failed: {key}")

            if rollback_on_success:
                rollback_results = self.service.rollback_to(marker)
                after_rollback = self._snapshot(validated)
                rollback_verified = all(self._same(after_rollback.get(key), value) for key, value in before.items())
                if not rollback_verified:
                    raise ForestControlError("Unified transaction rollback verification failed.")
            else:
                after_rollback = dict(after_write)
                rollback_verified = True

            return UnifiedTransactionResult(
                default_forest_name=default_forest_name,
                operation_count=len(operation_results),
                blocked_operation_count=0,
                rollback_step_count=len(rollback_results),
                write_verified=True,
                rollback_verified=rollback_verified,
                automatic_rollback=False,
                rolled_back_on_success=rollback_on_success,
                before_snapshot=before,
                after_write_snapshot=after_write,
                after_rollback_snapshot=after_rollback,
                operations=tuple(operation_results),
            )
        except Exception:
            if self.service.rollback_marker() > marker:
                automatic_rollback = True
                try:
                    self.service.rollback_to(marker)
                except Exception:
                    pass
            raise

    def apply_and_rollback(
        self,
        operations: Iterable[UnifiedControlOperation],
        *,
        default_forest_name: str | None = None,
    ) -> UnifiedTransactionResult:
        return self.execute(
            operations,
            default_forest_name=default_forest_name,
            rollback_on_success=True,
        )


class SemanticTransactionManager:
    def __init__(
        self,
        service: ForestPackControlService | None = None,
        api: "SemanticForestControlAPI | None" = None,
    ) -> None:
        self.service = service or ForestPackControlService()
        if api is None:
            from .semantic_api import SemanticForestControlAPI
            self.api = SemanticForestControlAPI(self.service)
        else:
            self.api = api

    def snapshot(
        self,
        forest_name: str,
        changes: Iterable[SemanticScalarChange],
    ) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        for change in changes:
            data = self.api.get(forest_name, change.domain, change.control, change.raw_property)
            snapshot[change.raw_property] = data["value"]
        return snapshot

    def validate_changes(
        self,
        changes: Iterable[SemanticScalarChange],
    ) -> tuple[SemanticScalarChange, ...]:
        validated = tuple(changes)
        if not validated:
            raise ForestControlError("Semantic transaction requires at least one change.")

        seen: set[str] = set()
        for change in validated:
            if change.raw_property in seen:
                raise ForestControlError(f"Duplicate semantic transaction property: {change.raw_property}")
            seen.add(change.raw_property)
            descriptor = self.api.describe(change.domain, change.control, change.raw_property)
            if descriptor.route != "scalar_direct":
                raise ForestControlError(
                    "Semantic transaction only accepts direct scalar routes: "
                    f"{change.domain}.{change.control}.{change.raw_property} route={descriptor.route}"
                )
        return validated

    def apply_and_rollback(
        self,
        forest_name: str,
        changes: Iterable[SemanticScalarChange],
    ) -> SemanticTransactionResult:
        validated = self.validate_changes(changes)
        before = self.snapshot(forest_name, validated)
        write_endpoint = callable(getattr(self.service, "set_property", None))
        rollback_endpoint = callable(getattr(self.service, "rollback", None))
        if not write_endpoint:
            after_write = self.snapshot(forest_name, validated)
            if after_write != before:
                raise ForestControlError(f"Semantic transaction runtime boundary changed state: {forest_name}")
            rollback_results = self.api.rollback()
            after_rollback = self.snapshot(forest_name, validated)
            rollback_verified = after_rollback == before
            if not rollback_verified:
                raise ForestControlError(f"Semantic transaction rollback boundary changed state: {forest_name}")
            return SemanticTransactionResult(
                forest_name=forest_name,
                operation_count=0,
                blocked_operation_count=len(validated),
                rollback_step_count=len(rollback_results),
                write_verified=False,
                rollback_verified=True,
                before_snapshot=before,
                after_write_snapshot=after_write,
                after_rollback_snapshot=after_rollback,
                runtime_write_endpoint=False,
                runtime_rollback_endpoint=rollback_endpoint,
            )
        operations: list[dict[str, Any]] = []
        try:
            for change in validated:
                operations.append(self.api.set_scalar(
                    forest_name, change.domain, change.control, change.raw_property, change.value
                ))
            after_write = self.snapshot(forest_name, validated)
            expected = {change.raw_property: change.value for change in validated}
            write_verified = after_write == expected
            if not write_verified:
                raise ForestControlError(f"Semantic transaction write verification failed: {forest_name}")
            rollback_results = self.api.rollback()
            after_rollback = self.snapshot(forest_name, validated)
            rollback_verified = after_rollback == before
            if not rollback_verified:
                raise ForestControlError(f"Semantic transaction rollback verification failed: {forest_name}")
            return SemanticTransactionResult(
                forest_name=forest_name,
                operation_count=len(operations),
                blocked_operation_count=0,
                rollback_step_count=len(rollback_results),
                write_verified=True,
                rollback_verified=True,
                before_snapshot=before,
                after_write_snapshot=after_write,
                after_rollback_snapshot=after_rollback,
                runtime_write_endpoint=True,
                runtime_rollback_endpoint=rollback_endpoint,
            )
        except Exception:
            try:
                self.api.rollback()
            except Exception:
                pass
            raise
