from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from forest_manager.max_bridge.runtime_bridge import read_selected_spline_segments


class WallEdgeAnnotationError(RuntimeError):
    pass


@dataclass(frozen=True)
class WallEdgeAnnotation:
    node_name: str
    spline_index: int
    segment_count: int
    wall_segments: tuple[int, ...]
    walkway_open_segments: tuple[int, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "node_name": self.node_name,
            "spline_index": self.spline_index,
            "segment_count": self.segment_count,
            "wall_segments": list(self.wall_segments),
            "walkway_open_segments": list(self.walkway_open_segments),
            "wall_edge_source": "artist_3ds_max_segment_selection",
            "default_unmarked_role": "walkway_open_edge",
            "verified": True,
        }


def normalize_wall_edge_annotation(payload: Mapping[str, Any], *, require_wall: bool = True) -> WallEdgeAnnotation:
    node_name = str(payload.get("node_name") or "").strip()
    spline_index = int(payload.get("spline_index") or 0)
    segment_count = int(payload.get("segment_count") or 0)
    if not node_name:
        raise WallEdgeAnnotationError("Wall Edge annotation requires a spline node name.")
    if spline_index != 1:
        raise WallEdgeAnnotationError("Stage 8 Wall Edge foundation currently supports one spline per Line.")
    if segment_count < 3:
        raise WallEdgeAnnotationError("Closed planting boundary must contain at least three segments.")

    raw = payload.get("selected_segments")
    if raw is None:
        raw = payload.get("wall_segments")
    if not isinstance(raw, (list, tuple)):
        raise WallEdgeAnnotationError("Selected spline segment payload is missing.")
    wall_segments = tuple(sorted({int(value) for value in raw}))
    if require_wall and not wall_segments:
        raise WallEdgeAnnotationError("Select one or more spline segments in 3ds Max before marking Wall Edge.")
    if any(value < 1 or value > segment_count for value in wall_segments):
        raise WallEdgeAnnotationError("Wall Edge segment index is outside the selected spline.")
    walkway = tuple(index for index in range(1, segment_count + 1) if index not in wall_segments)
    return WallEdgeAnnotation(node_name, spline_index, segment_count, wall_segments, walkway)


def capture_selected_wall_edge_annotation(*, preflight: bool = True) -> WallEdgeAnnotation:
    return normalize_wall_edge_annotation(read_selected_spline_segments(preflight=preflight))


def upsert_wall_edge_annotation(manifest: dict[str, Any], annotation: WallEdgeAnnotation) -> dict[str, Any]:
    site_annotations = manifest.get("site_annotations")
    if not isinstance(site_annotations, dict):
        site_annotations = {}
        manifest["site_annotations"] = site_annotations
    wall_edges = site_annotations.get("wall_edges")
    if not isinstance(wall_edges, dict):
        wall_edges = {}
        site_annotations["wall_edges"] = wall_edges
    wall_edges[annotation.node_name] = annotation.as_dict()
    return manifest


def remove_wall_edge_annotation(manifest: dict[str, Any], node_name: str) -> bool:
    site_annotations = manifest.get("site_annotations")
    if not isinstance(site_annotations, dict):
        return False
    wall_edges = site_annotations.get("wall_edges")
    if not isinstance(wall_edges, dict):
        return False
    return wall_edges.pop(str(node_name), None) is not None


def read_wall_edge_annotation(manifest: Mapping[str, Any], node_name: str) -> WallEdgeAnnotation | None:
    site_annotations = manifest.get("site_annotations")
    if not isinstance(site_annotations, Mapping):
        return None
    wall_edges = site_annotations.get("wall_edges")
    if not isinstance(wall_edges, Mapping):
        return None
    payload = wall_edges.get(str(node_name))
    if not isinstance(payload, Mapping):
        return None
    return normalize_wall_edge_annotation(payload, require_wall=False)
