from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .schema import AnnotationSource, SemanticAnnotation, SemanticRole


BOUNDARY_ROLES = frozenset(
    {
        SemanticRole.FRONT_BOUNDARY,
        SemanticRole.REAR_BOUNDARY,
        SemanticRole.SIDE_BOUNDARY,
        SemanticRole.STREET_EDGE,
        SemanticRole.BUILDING_EDGE,
        SemanticRole.WALL,
    }
)

AREA_ROLES = frozenset(
    {
        SemanticRole.DRIVEWAY,
        SemanticRole.PARKING,
        SemanticRole.PLANTING_BED,
        SemanticRole.LAWN,
        SemanticRole.SPECIES_ZONE,
        SemanticRole.CLUSTER_ZONE,
        SemanticRole.KEEP_CLEAR,
    }
)


def resolve_annotation(annotations: Iterable[SemanticAnnotation]) -> SemanticAnnotation | None:
    items = tuple(annotations)
    if not items:
        return None
    return max(items, key=lambda item: (item.priority, item.revision))


def next_revision(annotations: Iterable[SemanticAnnotation]) -> int:
    revisions = [int(item.revision) for item in annotations]
    return (max(revisions) if revisions else 0) + 1


def make_ai_annotation(
    geometry_id: str,
    role: SemanticRole | str,
    *,
    confidence: float | None = None,
    label: str = "",
    notes: str = "",
    reason: str = "",
    evidence: tuple[str, ...] = (),
    revision: int = 1,
) -> SemanticAnnotation:
    return SemanticAnnotation(
        geometry_id=str(geometry_id),
        role=role if isinstance(role, SemanticRole) else SemanticRole(str(role)),
        source=AnnotationSource.AI_INFERRED,
        confidence=confidence,
        label=label,
        notes=notes,
        reason=reason,
        evidence=evidence,
        revision=revision,
    )


def make_artist_annotation(
    geometry_id: str,
    role: SemanticRole | str,
    *,
    confirmed: bool,
    label: str = "",
    notes: str = "",
    revision: int = 1,
) -> SemanticAnnotation:
    return SemanticAnnotation(
        geometry_id=str(geometry_id),
        role=role if isinstance(role, SemanticRole) else SemanticRole(str(role)),
        source=AnnotationSource.ARTIST_CONFIRMED if confirmed else AnnotationSource.ARTIST_OVERRIDE,
        confidence=None,
        label=label,
        notes=notes,
        revision=revision,
    )


def with_revision(annotation: SemanticAnnotation, revision: int) -> SemanticAnnotation:
    return replace(annotation, revision=int(revision))


def is_boundary_role(role: SemanticRole | str) -> bool:
    semantic_role = role if isinstance(role, SemanticRole) else SemanticRole(str(role))
    return semantic_role in BOUNDARY_ROLES
