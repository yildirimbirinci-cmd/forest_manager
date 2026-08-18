from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


class SceneSpaceBoundaryError(RuntimeError):
    pass


@dataclass(frozen=True)
class SceneUnitSnapshot:
    display_type: str
    display_unit: str
    system_type: str
    system_scale: float
    one_meter_system_units: float
    one_centimeter_system_units: float
    one_millimeter_system_units: float

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SceneUnitSnapshot":
        one_meter = float(payload.get("one_meter_system_units") or 0.0)
        one_centimeter = float(payload.get("one_centimeter_system_units") or 0.0)
        one_millimeter = float(payload.get("one_millimeter_system_units") or 0.0)
        if one_meter <= 0.0 or one_centimeter <= 0.0 or one_millimeter <= 0.0:
            raise SceneSpaceBoundaryError("Scene unit conversion factors must be positive.")
        return cls(
            display_type=str(payload.get("display_type") or "").strip(),
            display_unit=str(payload.get("display_unit") or "").strip(),
            system_type=str(payload.get("system_type") or "").strip(),
            system_scale=float(payload.get("system_scale") or 0.0),
            one_meter_system_units=one_meter,
            one_centimeter_system_units=one_centimeter,
            one_millimeter_system_units=one_millimeter,
        )


@dataclass(frozen=True)
class SceneBoundarySnapshot:
    node_name: str
    node_class: str
    spline_count: int
    all_splines_closed: bool
    width_system_units: float
    depth_system_units: float
    height_system_units: float
    units: SceneUnitSnapshot

    @property
    def is_planar(self) -> bool:
        tolerance = max(
            self.units.one_millimeter_system_units,
            min(self.width_system_units, self.depth_system_units) * 1e-6,
        )
        return abs(self.height_system_units) <= tolerance

    @property
    def width_meters(self) -> float:
        return self.width_system_units / self.units.one_meter_system_units

    @property
    def depth_meters(self) -> float:
        return self.depth_system_units / self.units.one_meter_system_units

    def to_manifest_payload(self) -> dict[str, Any]:
        return {
            "node_name": self.node_name,
            "node_class": self.node_class,
            "spline_count": self.spline_count,
            "all_splines_closed": self.all_splines_closed,
            "width_system_units": self.width_system_units,
            "depth_system_units": self.depth_system_units,
            "height_system_units": self.height_system_units,
            "width_meters": self.width_meters,
            "depth_meters": self.depth_meters,
            "scene_units": {
                "display_type": self.units.display_type,
                "display_unit": self.units.display_unit,
                "system_type": self.units.system_type,
                "system_scale": self.units.system_scale,
                "one_meter_system_units": self.units.one_meter_system_units,
                "one_centimeter_system_units": self.units.one_centimeter_system_units,
                "one_millimeter_system_units": self.units.one_millimeter_system_units,
            },
            "coordinate_source": "selected_3ds_max_boundary",
            "reference_image_projection": False,
            "vertex_geometry_available": False,
        }


class SceneBoundaryRuntime:
    """Read-only Stage 8 gateway for the currently selected 3ds Max boundary.

    This intentionally does not turn the selected object's bounding box into a
    planting distribution. The measurement payload establishes identity, closed
    spline status, scene dimensions and unit conversion only. Exact scene-space
    remapping remains blocked until sampled/world spline vertices are exposed by
    the bridge.
    """

    def read_selected_boundary(self, *, preflight: bool = True) -> SceneBoundarySnapshot:
        if preflight:
            ensure_current_bridge()

        response = send_command("GET_SELECTION_MEASUREMENTS")
        if not isinstance(response, dict) or response.get("ok") is not True:
            raise SceneSpaceBoundaryError(
                "GET_SELECTION_MEASUREMENTS failed: "
                + str((response or {}).get("error") if isinstance(response, dict) else response)
            )

        data = response.get("data")
        if not isinstance(data, Mapping) or data.get("verified") is not True:
            raise SceneSpaceBoundaryError("Selection measurement payload was not verified.")

        if data.get("is_spline") is not True:
            raise SceneSpaceBoundaryError("Selected 3ds Max object is not a spline.")
        if data.get("all_splines_closed") is not True:
            raise SceneSpaceBoundaryError("Selected planting boundary must contain only closed splines.")

        node_name = str(data.get("node_name") or "").strip()
        if not node_name:
            raise SceneSpaceBoundaryError("Selected boundary has no scene node name.")

        spline_count = int(data.get("spline_count") or 0)
        width = float(data.get("width_system_units") or 0.0)
        depth = float(data.get("depth_system_units") or 0.0)
        height = float(data.get("height_system_units") or 0.0)
        if spline_count < 1:
            raise SceneSpaceBoundaryError("Selected boundary contains no spline.")
        if width <= 0.0 or depth <= 0.0:
            raise SceneSpaceBoundaryError("Selected boundary must have positive scene-space width and depth.")

        units_payload = data.get("scene_units")
        if not isinstance(units_payload, Mapping):
            raise SceneSpaceBoundaryError("Selection measurement payload has no scene-unit context.")

        snapshot = SceneBoundarySnapshot(
            node_name=node_name,
            node_class=str(data.get("node_class") or "").strip(),
            spline_count=spline_count,
            all_splines_closed=True,
            width_system_units=width,
            depth_system_units=depth,
            height_system_units=height,
            units=SceneUnitSnapshot.from_payload(units_payload),
        )
        if not snapshot.is_planar:
            raise SceneSpaceBoundaryError(
                "Selected planting boundary is not planar enough for Stage 8 scene-space distribution."
            )
        return snapshot


def build_scene_space_boundary_foundation(
    *,
    runtime: SceneBoundaryRuntime | None = None,
    preflight: bool = True,
) -> dict[str, Any]:
    gateway = runtime or SceneBoundaryRuntime()
    boundary = gateway.read_selected_boundary(preflight=preflight)
    return {
        "verified": True,
        "boundary": boundary.to_manifest_payload(),
        "distribution_policy": "scene_geometry_only",
        "reference_image_role": "semantic_design_guidance_only",
        "map_policy": "parked_not_projected_from_reference_image",
        "exact_polygon_remap_ready": False,
        "next_requirement": "bridge_world_space_spline_vertex_sampling",
        "scene_mutated": False,
    }
