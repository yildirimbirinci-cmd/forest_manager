from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .service import ForestPackControlService


DISTRIBUTION_SCALARS: tuple[str, ...] = (
    "units_x", "units_y", "pixels_x", "pixels_y", "lock_ratio", "distmapchan",
    "clusize", "clurough", "clunoise", "cluedge", "distpathmode", "distpathgeomid",
    "distpathspacing", "distpathoffset", "distpathrandpos", "distpathxfollow",
    "distpathzfollow", "distrefmode", "distrefgetrot", "distrefgetscale",
    "distrefnumitems", "distrefrandpos", "distrefmatid", "distrefmatchname",
    "distrefmatchregex",
)

DISTRIBUTION_COMPLEX: tuple[str, ...] = (
    "distmap", "densityMap", "distpathnodes", "distrefnodes",
)


@dataclass(frozen=True)
class DistributionState:
    forest_name: str
    values: Mapping[str, Any]


class DistributionAdapter:
    """Stage 5D.43 distribution adapter on the verified discovery-only bridge surface."""

    def __init__(self, service: ForestPackControlService | None = None) -> None:
        self.service = service or ForestPackControlService()

    def read_state(self, forest_name: str) -> DistributionState:
        inventory = self.service.inventory(forest_name)
        properties = {
            str(prop.get("name") or ""): prop
            for prop in (inventory.get("properties") or [])
            if isinstance(prop, Mapping)
        }
        values = {
            prop: (properties.get(prop) or {}).get("value")
            for prop in DISTRIBUTION_SCALARS + DISTRIBUTION_COMPLEX
        }
        return DistributionState(forest_name=forest_name, values=values)

    def no_op_scalar_plan(self, forest_name: str) -> dict[str, Any]:
        state = self.read_state(forest_name)
        return {prop: state.values.get(prop) for prop in DISTRIBUTION_SCALARS}

    def update_scalars(self, forest_name: str, values: Mapping[str, Any]) -> dict[str, Any]:
        unsupported = [prop for prop in values if prop not in DISTRIBUTION_SCALARS]
        if unsupported:
            raise ValueError(f"Unsupported distribution scalar: {unsupported[0]}")
        raise RuntimeError(
            "Distribution scalar write is unavailable in the verified runtime bridge; "
            "set_property/rollback write endpoints are not exposed by the current capability boundary."
        )
