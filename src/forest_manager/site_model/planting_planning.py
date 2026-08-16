from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from .schema import AnnotationSource, SemanticAnnotation, SemanticRole, SiteGeometry
from .service import SiteModelService
from .site_context import SiteContext, SiteContextInterpreter


class PlantingIntentKind(str, Enum):
    SPECIES = "species"
    CLUSTER = "cluster"
    PLANTING_BED = "planting_bed"
    LAWN = "lawn"
    EXCLUSION = "exclusion"


@dataclass(frozen=True)
class PlantingDirective:
    geometry_id: str
    intent: PlantingIntentKind
    semantic_role: SemanticRole
    source: AnnotationSource
    priority: int
    species: tuple[str, ...] = ()
    cluster_label: str = ""
    density_hint: str = ""
    notes: str = ""
    reason: str = ""
    evidence: tuple[str, ...] = ()
    boundary_context: tuple[SemanticRole, ...] = ()

    @property
    def artist_authored(self) -> bool:
        return self.source in {AnnotationSource.ARTIST_CONFIRMED, AnnotationSource.ARTIST_OVERRIDE}

    @property
    def blocks_planting(self) -> bool:
        return self.intent is PlantingIntentKind.EXCLUSION


@dataclass(frozen=True)
class PlantingPlan:
    revision: int
    directives: tuple[PlantingDirective, ...]
    exclusion_geometry_ids: tuple[str, ...]
    artist_directive_count: int
    ai_directive_count: int

    def directive_for(self, geometry_id: str) -> PlantingDirective | None:
        target = str(geometry_id)
        return next((item for item in self.directives if item.geometry_id == target), None)


_ROLE_TO_INTENT: Mapping[SemanticRole, PlantingIntentKind] = {
    SemanticRole.SPECIES_ZONE: PlantingIntentKind.SPECIES,
    SemanticRole.CLUSTER_ZONE: PlantingIntentKind.CLUSTER,
    SemanticRole.PLANTING_BED: PlantingIntentKind.PLANTING_BED,
    SemanticRole.LAWN: PlantingIntentKind.LAWN,
    SemanticRole.KEEP_CLEAR: PlantingIntentKind.EXCLUSION,
}

_BOUNDARY_ROLES = {
    SemanticRole.FRONT_BOUNDARY,
    SemanticRole.REAR_BOUNDARY,
    SemanticRole.SIDE_BOUNDARY,
    SemanticRole.BUILDING_EDGE,
    SemanticRole.WALL,
    SemanticRole.SIDEWALK,
    SemanticRole.STREET_EDGE,
}


class PlantingPlanningService:
    """Build a deterministic planting-intent plan from the resolved Site Model.

    The planner is deliberately separate from Forest Pack execution. It converts semantic
    site understanding into a stable planning contract that later placement/generation
    stages can consume. Artist-confirmed and artist-overridden annotations remain the
    resolved source of truth because SiteModelService.resolved_annotation applies source
    priority before this planner sees the data.
    """

    def build_plan(
        self,
        service: SiteModelService,
        *,
        geometry_ids: Iterable[str] | None = None,
    ) -> PlantingPlan:
        snapshot = service.snapshot()
        selected = None if geometry_ids is None else {str(item) for item in geometry_ids}
        resolved: dict[str, SemanticAnnotation] = {}
        resolved_roles: dict[str, SemanticRole] = {}
        geometry_map = {item.geometry_id: item for item in snapshot.geometries}

        for geometry in snapshot.geometries:
            annotation = service.resolved_annotation(geometry.geometry_id)
            if annotation is None:
                continue
            resolved[geometry.geometry_id] = annotation
            resolved_roles[geometry.geometry_id] = annotation.role

        context = SiteContextInterpreter().build(snapshot.geometries, resolved_roles=resolved_roles)
        directives: list[PlantingDirective] = []
        for geometry_id in sorted(resolved):
            if selected is not None and geometry_id not in selected:
                continue
            annotation = resolved[geometry_id]
            intent = _ROLE_TO_INTENT.get(annotation.role)
            if intent is None:
                continue
            directives.append(self._directive(geometry_map[geometry_id], annotation, intent, context, resolved_roles))

        # Exclusions are placed first for downstream consumers, then artist-authored
        # directives, then AI suggestions. This makes safety and artist intent explicit
        # without modifying the underlying annotation history.
        directives.sort(
            key=lambda item: (
                0 if item.blocks_planting else 1,
                -item.priority,
                item.geometry_id,
            )
        )
        exclusions = tuple(item.geometry_id for item in directives if item.blocks_planting)
        artist_count = sum(1 for item in directives if item.artist_authored)
        return PlantingPlan(
            revision=snapshot.revision,
            directives=tuple(directives),
            exclusion_geometry_ids=exclusions,
            artist_directive_count=artist_count,
            ai_directive_count=len(directives) - artist_count,
        )

    def _directive(
        self,
        geometry: SiteGeometry,
        annotation: SemanticAnnotation,
        intent: PlantingIntentKind,
        context: SiteContext,
        resolved_roles: Mapping[str, SemanticRole],
    ) -> PlantingDirective:
        metadata = geometry.metadata
        species = self._species(metadata)
        cluster_label = self._first_text(metadata, "cluster_label", "plant_group", "group_name", "cluster")
        density_hint = self._first_text(metadata, "density_hint", "planting_density", "density")
        notes = self._first_text(metadata, "planting_notes", "notes", "intent") or annotation.notes
        boundary_context = self._boundary_context(geometry.geometry_id, context, resolved_roles)
        reason = annotation.reason or self._default_reason(annotation, intent)
        evidence = tuple(annotation.evidence) + tuple(
            f"boundary_context={role.value}" for role in boundary_context
        )
        return PlantingDirective(
            geometry_id=geometry.geometry_id,
            intent=intent,
            semantic_role=annotation.role,
            source=annotation.source,
            priority=annotation.priority,
            species=species,
            cluster_label=cluster_label,
            density_hint=density_hint,
            notes=notes,
            reason=reason,
            evidence=evidence,
            boundary_context=boundary_context,
        )

    @staticmethod
    def _species(metadata: Mapping[str, Any]) -> tuple[str, ...]:
        value = None
        for key in ("species", "plant_species", "species_names", "plants"):
            if key in metadata and metadata[key] not in (None, "", (), []):
                value = metadata[key]
                break
        if value is None:
            return ()
        if isinstance(value, str):
            normalized = value.replace(";", ",")
            return tuple(item.strip() for item in normalized.split(",") if item.strip())
        if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
            return tuple(str(item).strip() for item in value if str(item).strip())
        return (str(value).strip(),) if str(value).strip() else ()

    @staticmethod
    def _first_text(metadata: Mapping[str, Any], *keys: str) -> str:
        for key in keys:
            value = metadata.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    @staticmethod
    def _default_reason(annotation: SemanticAnnotation, intent: PlantingIntentKind) -> str:
        if annotation.source in {AnnotationSource.ARTIST_CONFIRMED, AnnotationSource.ARTIST_OVERRIDE}:
            return f"artist_{intent.value}_intent"
        return f"ai_{intent.value}_intent"

    @staticmethod
    def _boundary_context(
        geometry_id: str,
        context: SiteContext,
        resolved_roles: Mapping[str, SemanticRole],
    ) -> tuple[SemanticRole, ...]:
        target = context.facts.get(geometry_id)
        if target is None:
            return ()
        scale = max(context.width, context.height, 1.0)
        threshold = scale * 0.12
        nearby: set[SemanticRole] = set()
        for other_id, other in context.facts.items():
            if other_id == geometry_id:
                continue
            role = resolved_roles.get(other_id)
            if role not in _BOUNDARY_ROLES:
                continue
            dx = target.center_x - other.center_x
            dy = target.center_y - other.center_y
            if (dx * dx + dy * dy) ** 0.5 <= threshold:
                nearby.add(role)
        return tuple(sorted(nearby, key=lambda item: item.value))


__all__ = [
    "PlantingDirective",
    "PlantingIntentKind",
    "PlantingPlan",
    "PlantingPlanningService",
]
