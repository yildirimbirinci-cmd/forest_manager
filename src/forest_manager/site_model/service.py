from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable

from .annotations import make_ai_annotation, make_artist_annotation, next_revision, resolve_annotation
from .persistence import SiteModelPersistence
from .schema import AnnotationSource, SemanticAnnotation, SemanticRole, SiteGeometry, SiteModelSnapshot


class SiteModelError(RuntimeError):
    pass


class SiteModelService:
    VERSION = 1

    def __init__(self, *, persistence: SiteModelPersistence | None = None) -> None:
        self.persistence = persistence or SiteModelPersistence()
        self._geometries: dict[str, SiteGeometry] = {}
        self._annotations: dict[str, list[SemanticAnnotation]] = {}
        self._revision = 0

    @property
    def revision(self) -> int:
        return self._revision

    def snapshot(self) -> SiteModelSnapshot:
        geometries = tuple(self._geometries[key] for key in sorted(self._geometries))
        annotations = tuple(
            annotation
            for key in sorted(self._annotations)
            for annotation in sorted(self._annotations[key], key=lambda item: item.revision)
        )
        return SiteModelSnapshot(self.VERSION, self._revision, geometries, annotations)

    def restore(self, snapshot: SiteModelSnapshot) -> SiteModelSnapshot:
        geometries = {item.geometry_id: item for item in snapshot.geometries}
        annotations: dict[str, list[SemanticAnnotation]] = {}
        for annotation in snapshot.annotations:
            if annotation.geometry_id not in geometries:
                raise SiteModelError(f"annotation references missing geometry: {annotation.geometry_id}")
            annotations.setdefault(annotation.geometry_id, []).append(annotation)
        self._geometries = geometries
        self._annotations = annotations
        self._revision = int(snapshot.revision)
        return self.snapshot()

    def save(self, path: str | Path) -> Path:
        return self.persistence.save(path, self.snapshot())

    def load(self, path: str | Path) -> SiteModelSnapshot:
        snapshot = self.persistence.load(path)
        return self.restore(snapshot)

    def upsert_geometry(self, geometry: SiteGeometry) -> SiteGeometry:
        self._geometries[geometry.geometry_id] = geometry
        self._revision += 1
        return geometry

    def geometry(self, geometry_id: str) -> SiteGeometry:
        try:
            return self._geometries[str(geometry_id)]
        except KeyError as exc:
            raise SiteModelError(f"unknown site geometry: {geometry_id}") from exc

    def annotations_for(self, geometry_id: str) -> tuple[SemanticAnnotation, ...]:
        self.geometry(geometry_id)
        return tuple(sorted(self._annotations.get(str(geometry_id), ()), key=lambda item: item.revision))

    def resolved_annotation(self, geometry_id: str) -> SemanticAnnotation | None:
        return resolve_annotation(self.annotations_for(geometry_id))

    def _append_annotation(self, annotation: SemanticAnnotation) -> SemanticAnnotation:
        self.geometry(annotation.geometry_id)
        existing = self._annotations.setdefault(annotation.geometry_id, [])
        updated = replace(annotation, revision=next_revision(existing))
        existing.append(updated)
        self._revision += 1
        return updated

    def apply_ai_annotation(
        self,
        geometry_id: str,
        role: SemanticRole | str,
        *,
        confidence: float | None = None,
        label: str = "",
        notes: str = "",
    ) -> SemanticAnnotation:
        annotation = make_ai_annotation(
            geometry_id,
            role,
            confidence=confidence,
            label=label,
            notes=notes,
        )
        return self._append_annotation(annotation)

    def apply_artist_confirmation(
        self,
        geometry_id: str,
        role: SemanticRole | str | None = None,
        *,
        label: str = "",
        notes: str = "",
    ) -> SemanticAnnotation:
        current = self.resolved_annotation(geometry_id)
        selected_role = role if role is not None else (current.role if current is not None else None)
        if selected_role is None:
            raise SiteModelError("artist confirmation requires an existing or explicit semantic role")
        annotation = make_artist_annotation(
            geometry_id,
            selected_role,
            confirmed=True,
            label=label,
            notes=notes,
        )
        return self._append_annotation(annotation)

    def apply_artist_override(
        self,
        geometry_id: str,
        role: SemanticRole | str,
        *,
        label: str = "",
        notes: str = "",
    ) -> SemanticAnnotation:
        annotation = make_artist_annotation(
            geometry_id,
            role,
            confirmed=False,
            label=label,
            notes=notes,
        )
        return self._append_annotation(annotation)

    def reanalyze_ai(self, annotations: Iterable[SemanticAnnotation]) -> None:
        """Replace AI suggestions while retaining artist-authored corrections.

        Each incoming item must be AI_INFERRED. Artist-confirmed/overridden
        annotations already stored for the geometry are intentionally preserved.
        """
        grouped: dict[str, list[SemanticAnnotation]] = {}
        for annotation in annotations:
            if annotation.source is not AnnotationSource.AI_INFERRED:
                raise SiteModelError("AI reanalysis accepts only ai_inferred annotations")
            self.geometry(annotation.geometry_id)
            grouped.setdefault(annotation.geometry_id, []).append(annotation)

        for geometry_id, incoming in grouped.items():
            retained = [
                item
                for item in self._annotations.get(geometry_id, [])
                if item.source is not AnnotationSource.AI_INFERRED
            ]
            next_value = next_revision(retained)
            refreshed: list[SemanticAnnotation] = []
            for annotation in incoming:
                refreshed.append(replace(annotation, revision=next_value))
                next_value += 1
            self._annotations[geometry_id] = retained + refreshed
            self._revision += 1
