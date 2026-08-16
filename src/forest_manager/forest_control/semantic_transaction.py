from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

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


class SemanticTransactionManager:
    def __init__(
        self,
        service: ForestPackControlService | None = None,
        api: SemanticForestControlAPI | None = None,
    ) -> None:
        self.service = service or ForestPackControlService()
        self.api = api or SemanticForestControlAPI(self.service)

    def snapshot(
        self,
        forest_name: str,
        changes: Iterable[SemanticScalarChange],
    ) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        for change in changes:
            data = self.api.get(
                forest_name,
                change.domain,
                change.control,
                change.raw_property,
            )
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
                raise ForestControlError(
                    f"Duplicate semantic transaction property: {change.raw_property}"
                )
            seen.add(change.raw_property)

            descriptor = self.api.describe(
                change.domain,
                change.control,
                change.raw_property,
            )
            if descriptor.route != "scalar_direct":
                raise ForestControlError(
                    "Semantic transaction only accepts direct scalar routes: "
                    f"{change.domain}.{change.control}.{change.raw_property} "
                    f"route={descriptor.route}"
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
                raise ForestControlError(
                    f"Semantic transaction runtime boundary changed state: {forest_name}"
                )
            rollback_results = self.api.rollback()
            after_rollback = self.snapshot(forest_name, validated)
            rollback_verified = after_rollback == before
            if not rollback_verified:
                raise ForestControlError(
                    f"Semantic transaction rollback boundary changed state: {forest_name}"
                )
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
                operations.append(
                    self.api.set_scalar(
                        forest_name,
                        change.domain,
                        change.control,
                        change.raw_property,
                        change.value,
                    )
                )

            after_write = self.snapshot(forest_name, validated)
            expected = {change.raw_property: change.value for change in validated}
            write_verified = after_write == expected
            if not write_verified:
                raise ForestControlError(
                    f"Semantic transaction write verification failed: {forest_name}"
                )

            rollback_results = self.api.rollback()
            after_rollback = self.snapshot(forest_name, validated)
            rollback_verified = after_rollback == before
            if not rollback_verified:
                raise ForestControlError(
                    f"Semantic transaction rollback verification failed: {forest_name}"
                )

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
