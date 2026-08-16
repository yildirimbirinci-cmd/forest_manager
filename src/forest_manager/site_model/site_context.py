from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Iterable, Mapping

from .schema import GeometryKind, SemanticRole, SiteGeometry


@dataclass(frozen=True)
class GeometrySpatialFacts:
    geometry_id: str
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    center_x: float
    center_y: float
    width: float
    height: float


@dataclass(frozen=True)
class SiteContext:
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    center_x: float
    center_y: float
    facts: Mapping[str, GeometrySpatialFacts]
    resolved_roles: Mapping[str, SemanticRole]
    frontage_axis: str | None = None
    frontage_side: str | None = None
    frontage_anchor_ids: tuple[str, ...] = ()
    building_anchor_ids: tuple[str, ...] = ()

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y


@dataclass(frozen=True)
class ContextualSemanticInference:
    geometry_id: str
    role: SemanticRole
    confidence: float
    reason: str
    evidence: tuple[str, ...]


_FRONTAGE_ROLES = {
    SemanticRole.STREET_EDGE,
    SemanticRole.SIDEWALK,
    SemanticRole.FRONT_BOUNDARY,
}
_BUILDING_ROLES = {SemanticRole.BUILDING_EDGE}
_BOUNDARY_ROLES = {
    SemanticRole.FRONT_BOUNDARY,
    SemanticRole.REAR_BOUNDARY,
    SemanticRole.SIDE_BOUNDARY,
}


class SiteContextInterpreter:
    """Build deterministic spatial context and infer roles from geometry relationships.

    This layer intentionally uses only geometry and already resolved semantic anchors. It
    does not override source-metadata matches or artist annotations; callers decide the
    precedence. The goal is to provide a stable spatial contract for later AI backends.
    """

    def build(
        self,
        geometries: Iterable[SiteGeometry],
        *,
        resolved_roles: Mapping[str, SemanticRole] | None = None,
    ) -> SiteContext:
        items = tuple(geometries)
        if not items:
            return SiteContext(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, {}, dict(resolved_roles or {}))
        facts = {item.geometry_id: self.spatial_facts(item) for item in items}
        min_x = min(item.min_x for item in facts.values())
        min_y = min(item.min_y for item in facts.values())
        max_x = max(item.max_x for item in facts.values())
        max_y = max(item.max_y for item in facts.values())
        roles = dict(resolved_roles or {})
        frontage_ids = tuple(sorted(gid for gid, role in roles.items() if role in _FRONTAGE_ROLES and gid in facts))
        building_ids = tuple(sorted(gid for gid, role in roles.items() if role in _BUILDING_ROLES and gid in facts))
        axis, side = self._frontage_orientation(facts, frontage_ids, min_x, min_y, max_x, max_y)
        return SiteContext(
            min_x,
            min_y,
            max_x,
            max_y,
            (min_x + max_x) / 2.0,
            (min_y + max_y) / 2.0,
            facts,
            roles,
            axis,
            side,
            frontage_ids,
            building_ids,
        )

    def infer(self, geometry: SiteGeometry, context: SiteContext) -> ContextualSemanticInference | None:
        facts = context.facts.get(geometry.geometry_id)
        if facts is None:
            return None
        current_role = context.resolved_roles.get(geometry.geometry_id)
        if current_role in _BOUNDARY_ROLES:
            return None

        if geometry.kind in {GeometryKind.LINE, GeometryKind.POLYLINE}:
            boundary = self._infer_boundary(facts, context)
            if boundary is not None:
                return boundary

        if geometry.kind in {GeometryKind.REGION, GeometryKind.HATCH} and geometry.closed:
            access = self._infer_vehicle_access(facts, context)
            if access is not None:
                return access
        return None

    @staticmethod
    def spatial_facts(geometry: SiteGeometry) -> GeometrySpatialFacts:
        xs = [point.x for point in geometry.points]
        ys = [point.y for point in geometry.points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        return GeometrySpatialFacts(
            geometry.geometry_id,
            min_x,
            min_y,
            max_x,
            max_y,
            (min_x + max_x) / 2.0,
            (min_y + max_y) / 2.0,
            max_x - min_x,
            max_y - min_y,
        )

    def _infer_boundary(self, facts: GeometrySpatialFacts, context: SiteContext) -> ContextualSemanticInference | None:
        if not context.frontage_axis or not context.frontage_side:
            return None
        scale = max(context.width, context.height, 1.0)
        edge_tol = max(scale * 0.08, 1e-6)
        side = self._envelope_side(facts, context, edge_tol)
        if side is None:
            return None
        frontage_side = context.frontage_side
        opposite = {"min_x": "max_x", "max_x": "min_x", "min_y": "max_y", "max_y": "min_y"}[frontage_side]
        if side == frontage_side:
            return ContextualSemanticInference(
                facts.geometry_id,
                SemanticRole.FRONT_BOUNDARY,
                0.82,
                "site_context_frontage_adjacency",
                (f"frontage_side={frontage_side}", f"frontage_anchors={len(context.frontage_anchor_ids)}"),
            )
        if side == opposite:
            return ContextualSemanticInference(
                facts.geometry_id,
                SemanticRole.REAR_BOUNDARY,
                0.74,
                "site_context_opposite_frontage",
                (f"frontage_side={frontage_side}", f"opposite_side={opposite}"),
            )
        return ContextualSemanticInference(
            facts.geometry_id,
            SemanticRole.SIDE_BOUNDARY,
            0.69,
            "site_context_lateral_envelope",
            (f"frontage_side={frontage_side}", f"boundary_side={side}"),
        )

    def _infer_vehicle_access(self, facts: GeometrySpatialFacts, context: SiteContext) -> ContextualSemanticInference | None:
        if not context.frontage_anchor_ids or not context.building_anchor_ids:
            return None
        frontage_distance = min(self._distance(facts, context.facts[item]) for item in context.frontage_anchor_ids)
        building_distance = min(self._distance(facts, context.facts[item]) for item in context.building_anchor_ids)
        scale = max(context.width, context.height, 1.0)
        near_frontage = frontage_distance <= scale * 0.18
        near_building = building_distance <= scale * 0.22
        long_side = max(facts.width, facts.height)
        short_side = max(min(facts.width, facts.height), 1e-9)
        elongated = long_side / short_side >= 1.8
        if near_frontage and near_building and elongated:
            return ContextualSemanticInference(
                facts.geometry_id,
                SemanticRole.DRIVEWAY,
                0.68,
                "site_context_vehicle_access_connector",
                (
                    f"frontage_distance={frontage_distance:.3f}",
                    f"building_distance={building_distance:.3f}",
                    f"aspect_ratio={long_side / short_side:.2f}",
                ),
            )
        if near_frontage and facts.width > 0 and facts.height > 0 and not elongated:
            return ContextualSemanticInference(
                facts.geometry_id,
                SemanticRole.PARKING,
                0.56,
                "site_context_frontage_vehicle_area",
                (f"frontage_distance={frontage_distance:.3f}", "closed_area=true"),
            )
        return None

    @staticmethod
    def _distance(a: GeometrySpatialFacts, b: GeometrySpatialFacts) -> float:
        return hypot(a.center_x - b.center_x, a.center_y - b.center_y)

    @staticmethod
    def _envelope_side(facts: GeometrySpatialFacts, context: SiteContext, tolerance: float) -> str | None:
        # A horizontal boundary should be compared with the top/bottom envelope, while
        # a vertical boundary should be compared with the left/right envelope. This
        # avoids endpoint contact with a corner being mistaken for the boundary side.
        if facts.width >= facts.height:
            candidates = (
                (abs(facts.center_y - context.min_y), "min_y"),
                (abs(facts.center_y - context.max_y), "max_y"),
            )
        else:
            candidates = (
                (abs(facts.center_x - context.min_x), "min_x"),
                (abs(facts.center_x - context.max_x), "max_x"),
            )
        distance, side = min(candidates, key=lambda item: item[0])
        return side if distance <= tolerance else None

    @staticmethod
    def _frontage_orientation(
        facts: Mapping[str, GeometrySpatialFacts],
        frontage_ids: tuple[str, ...],
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
    ) -> tuple[str | None, str | None]:
        if not frontage_ids:
            return None, None
        center_x = sum(facts[item].center_x for item in frontage_ids) / len(frontage_ids)
        center_y = sum(facts[item].center_y for item in frontage_ids) / len(frontage_ids)
        distances = (
            (abs(center_x - min_x), "x", "min_x"),
            (abs(center_x - max_x), "x", "max_x"),
            (abs(center_y - min_y), "y", "min_y"),
            (abs(center_y - max_y), "y", "max_y"),
        )
        _, axis, side = min(distances, key=lambda item: item[0])
        return axis, side
