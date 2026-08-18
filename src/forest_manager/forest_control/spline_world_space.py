from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command

class SplineWorldSpaceError(RuntimeError):
    pass

@dataclass(frozen=True)
class WorldPoint:
    x: float
    y: float
    z: float

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "WorldPoint":
        return cls(x=float(payload["x"]), y=float(payload["y"]), z=float(payload["z"]))

@dataclass(frozen=True)
class WorldSpline:
    spline_index: int
    closed: bool
    knots: tuple[WorldPoint, ...]
    samples: tuple[WorldPoint, ...]

@dataclass(frozen=True)
class SelectedSplineWorldSpace:
    node_name: str
    node_class: str
    coordinate_system: str
    spline_count: int
    samples_per_spline: int
    splines: tuple[WorldSpline, ...]
    scene_units: Mapping[str, Any]

    @property
    def all_closed(self) -> bool:
        return bool(self.splines) and all(s.closed for s in self.splines)

    @property
    def total_knot_count(self) -> int:
        return sum(len(s.knots) for s in self.splines)

def _points(values: Iterable[Mapping[str, Any]]) -> tuple[WorldPoint, ...]:
    return tuple(WorldPoint.from_payload(v) for v in values)

def read_selected_spline_world_space(*, samples_per_spline: int = 64, preflight: bool = True) -> SelectedSplineWorldSpace:
    samples_per_spline = int(samples_per_spline)
    if not 8 <= samples_per_spline <= 512:
        raise ValueError("samples_per_spline must be between 8 and 512.")
    if preflight:
        ensure_current_bridge()

    response = send_command(f"GET_SELECTION_SPLINE_WORLD_SPACE|{samples_per_spline}")
    if not isinstance(response, dict) or response.get("ok") is not True:
        error = response.get("error") if isinstance(response, dict) else response
        raise SplineWorldSpaceError("World-space spline read failed: " + str(error))

    data = response.get("data")
    if not isinstance(data, Mapping) or data.get("verified") is not True:
        raise SplineWorldSpaceError("World-space spline payload was not verified.")
    if data.get("read_only") is not True:
        raise SplineWorldSpaceError("World-space spline command must remain read-only.")
    if str(data.get("coordinate_system") or "").lower() != "world":
        raise SplineWorldSpaceError("Spline coordinates are not explicitly world-space.")
    if data.get("all_splines_closed") is not True:
        raise SplineWorldSpaceError("Selected planting boundary must contain only closed splines.")

    raw_splines = data.get("splines")
    if not isinstance(raw_splines, list) or not raw_splines:
        raise SplineWorldSpaceError("World-space spline payload contains no spline geometry.")

    splines = []
    for raw in raw_splines:
        if not isinstance(raw, Mapping):
            raise SplineWorldSpaceError("Invalid spline geometry entry.")
        knots = _points(raw.get("knots_world") or [])
        samples = _points(raw.get("samples_world") or [])
        if len(knots) < 3:
            raise SplineWorldSpaceError("Closed planting boundary requires at least three knots.")
        if len(samples) != samples_per_spline:
            raise SplineWorldSpaceError("Spline sample count does not match the requested count.")
        splines.append(WorldSpline(
            spline_index=int(raw.get("spline_index") or 0),
            closed=raw.get("closed") is True,
            knots=knots,
            samples=samples,
        ))

    result = SelectedSplineWorldSpace(
        node_name=str(data.get("node_name") or "").strip(),
        node_class=str(data.get("node_class") or "").strip(),
        coordinate_system="world",
        spline_count=int(data.get("spline_count") or 0),
        samples_per_spline=int(data.get("samples_per_spline") or 0),
        splines=tuple(splines),
        scene_units=data.get("scene_units") or {},
    )
    if not result.node_name:
        raise SplineWorldSpaceError("Selected spline has no node name.")
    if result.spline_count != len(result.splines):
        raise SplineWorldSpaceError("Spline count does not match returned geometry.")
    if result.samples_per_spline != samples_per_spline:
        raise SplineWorldSpaceError("Returned sample policy does not match request.")
    if not result.all_closed:
        raise SplineWorldSpaceError("Returned spline geometry is not fully closed.")
    return result
