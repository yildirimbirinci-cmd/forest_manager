from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .area_records import AreaBoundaryRecord, AreaBoundaryRecordAdapter, AreaBoundaryUpdate
from .service import ForestControlError


@dataclass(frozen=True)
class BoundaryBehaviorPlan:
    choice: str
    area_index: int
    area_name: str
    update: AreaBoundaryUpdate | None
    blocked_reasons: tuple[str, ...] = ()
    ai_primary: bool = True
    artist_override_supported: bool = True
    status: str = "candidate"

    @property
    def executable(self) -> bool:
        return self.update is not None and not self.blocked_reasons


class BoundaryBehaviorPlanner:
    """Semantic boundary intent over one synchronized Forest Pack Area record.

    Stage 7.12 intentionally limits executable behavior to contracts supported by
    the Area rollout semantics already exposed by the verified record adapter:
    disabling falloff for a hard/clean edge, or enabling full density/scale
    falloff strength while preserving the existing positive boundary range for
    a soft edge. More expressive spill/screen behaviors require curve inversion
    and/or per-area distribution capabilities and therefore remain blocked.
    """

    CHOICES = ("Clean Edge", "Soft Edge", "Natural Spill", "Dense Screening")

    def __init__(self, adapter: AreaBoundaryRecordAdapter | None = None) -> None:
        self.adapter = adapter or AreaBoundaryRecordAdapter()

    @staticmethod
    def _positive_float(value: Any, field_name: str) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ForestControlError(f"Area {field_name} is not numeric.") from exc
        if result <= 0.0:
            raise ForestControlError(f"Area {field_name} must be positive for Soft Edge.")
        return result

    def plan_record(self, record: AreaBoundaryRecord, choice: str) -> BoundaryBehaviorPlan:
        token = str(choice).strip()
        if token not in self.CHOICES:
            raise ForestControlError(f"Unknown Boundary Behavior: {choice}")

        if token == "Clean Edge":
            return BoundaryBehaviorPlan(
                choice=token,
                area_index=record.index,
                area_name=record.name,
                update=AreaBoundaryUpdate(density_falloff=0.0, scale_falloff=0.0),
            )

        if token == "Soft Edge":
            width = self._positive_float(record.width, "boundary range")
            return BoundaryBehaviorPlan(
                choice=token,
                area_index=record.index,
                area_name=record.name,
                update=AreaBoundaryUpdate(width=width, density_falloff=100.0, scale_falloff=100.0),
            )

        if token == "Natural Spill":
            return BoundaryBehaviorPlan(
                choice=token,
                area_index=record.index,
                area_name=record.name,
                update=None,
                blocked_reasons=("requires_area_falloff_curve_inversion_capability",),
            )

        return BoundaryBehaviorPlan(
            choice=token,
            area_index=record.index,
            area_name=record.name,
            update=None,
            blocked_reasons=("requires_per_area_density_distribution_and_screening_capability",),
        )

    def plan(self, forest_name: str, area_index: int, choice: str) -> BoundaryBehaviorPlan:
        record = self.adapter.read_record(forest_name, area_index)
        return self.plan_record(record, choice)

    def apply(
        self,
        forest_name: str,
        area_index: int,
        choice: str,
        *,
        rollback_on_success: bool = False,
    ):
        plan = self.plan(forest_name, area_index, choice)
        if not plan.executable or plan.update is None:
            detail = ", ".join(plan.blocked_reasons) or "no executable Area update"
            raise ForestControlError(f"Boundary Behavior '{choice}' is not executable: {detail}")
        return self.adapter.apply_update(
            forest_name,
            area_index,
            plan.update,
            rollback_on_success=rollback_on_success,
        )
