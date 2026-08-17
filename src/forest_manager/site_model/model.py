from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BoundaryRole(str, Enum):
    PLANTING_BOUNDARY = "planting_boundary"
    FRONT_BOUNDARY = "front_boundary"
    REAR_BOUNDARY = "rear_boundary"
    SIDE_BOUNDARY = "side_boundary"
    BUILDING_EDGE = "building_edge"
    SIDEWALK = "sidewalk"
    DRIVEWAY = "driveway"
    PARKING = "parking"
    KEEP_CLEAR = "keep_clear"


@dataclass(frozen=True)
class SiteBoundary:
    node_name: str
    role: BoundaryRole = BoundaryRole.PLANTING_BOUNDARY
    area_square_meters: float = 0.0
    width_system_units: float = 0.0
    depth_system_units: float = 0.0
    spline_count: int = 1
    forest_manager_owned: bool = False

    @classmethod
    def from_bridge(cls, payload: dict[str, Any]) -> "SiteBoundary":
        return cls(
            node_name=str(payload.get("node_name") or ""),
            area_square_meters=float(payload.get("area_square_meters") or 0.0),
            width_system_units=float(payload.get("width_system_units") or 0.0),
            depth_system_units=float(payload.get("depth_system_units") or 0.0),
            spline_count=int(payload.get("spline_count") or 1),
            forest_manager_owned=bool(payload.get("forest_manager_owned")),
        )


@dataclass(frozen=True)
class SiteModel:
    primary_boundary: SiteBoundary
    boundaries: tuple[SiteBoundary, ...]
    scene_units: dict[str, Any] = field(default_factory=dict)
    source_kind: str = "3ds_max_scene"
    reference_image_path: str | None = None


@dataclass(frozen=True)
class PlantingGroupIntent:
    group_id: str
    label: str
    order: int
    semantic_role: str
    coverage_weight: float
    source_names: tuple[str, ...] = ()
    naturalness: str = "Balanced"
    cluster_character: str = "Medium Clusters"
    zone_mask_path: str | None = None
    visual_confidence: float = 0.0


@dataclass(frozen=True)
class PlantingPlan:
    site_model: SiteModel
    forest_name: str
    groups: tuple[PlantingGroupIntent, ...]
    reference_image_path: str | None = None
    generated_by: str = "stage8_foundation"

    @property
    def execution_ready(self) -> bool:
        return bool(self.groups) and all(group.source_names for group in self.groups)

    @property
    def visual_intent_ready(self) -> bool:
        return bool(self.groups) and all(group.zone_mask_path for group in self.groups)
