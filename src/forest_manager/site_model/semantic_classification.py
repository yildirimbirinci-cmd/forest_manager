from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

from .annotations import make_ai_annotation
from .schema import AnnotationSource, GeometryKind, SemanticAnnotation, SemanticRole, SiteGeometry
from .service import SiteModelService
from .site_context import SiteContext, SiteContextInterpreter


@dataclass(frozen=True)
class SemanticClassification:
    geometry_id: str
    role: SemanticRole
    confidence: float
    reason: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArtistFeedbackRule:
    signature: str
    role: SemanticRole
    sample_count: int
    source_geometry_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SemanticAnalysisResult:
    classified_geometry_ids: tuple[str, ...]
    feedback_rule_count: int


_ROLE_TOKENS: tuple[tuple[SemanticRole, tuple[str, ...]], ...] = (
    (SemanticRole.FRONT_BOUNDARY, ("front boundary", "front_boundary", "frontbound", "front edge")),
    (SemanticRole.REAR_BOUNDARY, ("rear boundary", "rear_boundary", "back boundary", "rear edge")),
    (SemanticRole.SIDE_BOUNDARY, ("side boundary", "side_boundary", "side edge")),
    (SemanticRole.SIDEWALK, ("sidewalk", "footpath", "pavement", "walkway")),
    (SemanticRole.STREET_EDGE, ("street edge", "street_edge", "road edge", "curb", "kerb")),
    (SemanticRole.DRIVEWAY, ("driveway", "drive way", "vehicle access")),
    (SemanticRole.PARKING, ("parking", "car park", "carpark")),
    (SemanticRole.BUILDING_EDGE, ("building edge", "building_edge", "building outline", "footprint")),
    (SemanticRole.WALL, ("wall", "garden wall", "retaining wall")),
    (SemanticRole.PLANTING_BED, ("planting bed", "planting_bed", "flower bed", "shrub bed")),
    (SemanticRole.LAWN, ("lawn", "grass", "turf")),
    (SemanticRole.SPECIES_ZONE, ("species zone", "species_zone", "species")),
    (SemanticRole.CLUSTER_ZONE, ("cluster zone", "cluster_zone", "cluster")),
    (SemanticRole.KEEP_CLEAR, ("keep clear", "keep_clear", "no planting", "exclusion")),
)


class SemanticClassificationPipeline:
    """Deterministic Stage 8 semantic classifier with persisted artist-feedback reuse.

    The classifier is intentionally backend-neutral. It provides a safe baseline now and
    a stable contract for a future vision/LLM classifier. Artist-authored annotations are
    never replaced by this class; SiteModelService.reanalyze_ai preserves them.
    """

    def analyze(self, service: SiteModelService, geometry_ids: Iterable[str] | None = None) -> SemanticAnalysisResult:
        snapshot = service.snapshot()
        selected = None if geometry_ids is None else {str(item) for item in geometry_ids}
        rules = self.build_artist_feedback_rules(service)
        context = self.build_site_context(service)
        annotations: list[SemanticAnnotation] = []
        classified: list[str] = []
        for geometry in snapshot.geometries:
            if selected is not None and geometry.geometry_id not in selected:
                continue
            result = self.classify_geometry(geometry, feedback_rules=rules, site_context=context)
            annotations.append(
                make_ai_annotation(
                    geometry.geometry_id,
                    result.role,
                    confidence=result.confidence,
                    label=result.role.value.replace("_", " ").title(),
                    notes="Stage 8 semantic classification",
                    reason=result.reason,
                    evidence=result.evidence,
                )
            )
            classified.append(geometry.geometry_id)
        if annotations:
            service.reanalyze_ai(annotations)
        return SemanticAnalysisResult(tuple(classified), len(rules))

    def classify_geometry(
        self,
        geometry: SiteGeometry,
        *,
        feedback_rules: Iterable[ArtistFeedbackRule] = (),
        site_context: SiteContext | None = None,
    ) -> SemanticClassification:
        signature = self.geometry_signature(geometry)
        feedback = {rule.signature: rule for rule in feedback_rules}.get(signature)
        if feedback is not None and geometry.geometry_id not in feedback.source_geometry_ids:
            return SemanticClassification(
                geometry.geometry_id,
                feedback.role,
                0.98,
                "artist_feedback",
                (f"signature={signature}", f"samples={feedback.sample_count}"),
            )

        text = self._semantic_text(geometry)
        for role, tokens in _ROLE_TOKENS:
            hits = tuple(token for token in tokens if token in text)
            if hits:
                confidence = min(0.96, 0.76 + 0.05 * len(hits))
                return SemanticClassification(
                    geometry.geometry_id,
                    role,
                    confidence,
                    "source_metadata_match",
                    tuple(f"token={item}" for item in hits),
                )

        if site_context is not None:
            contextual = SiteContextInterpreter().infer(geometry, site_context)
            if contextual is not None:
                return SemanticClassification(
                    geometry.geometry_id,
                    contextual.role,
                    contextual.confidence,
                    contextual.reason,
                    contextual.evidence,
                )

        if geometry.kind in {GeometryKind.REGION, GeometryKind.HATCH} and geometry.closed:
            return SemanticClassification(
                geometry.geometry_id,
                SemanticRole.PLANTING_BED,
                0.42,
                "closed_area_geometry_prior",
                (f"kind={geometry.kind.value}", "closed=true"),
            )
        if geometry.kind in {GeometryKind.LINE, GeometryKind.POLYLINE}:
            return SemanticClassification(
                geometry.geometry_id,
                SemanticRole.UNKNOWN,
                0.25,
                "linear_geometry_without_semantic_evidence",
                (f"kind={geometry.kind.value}",),
            )
        return SemanticClassification(
            geometry.geometry_id,
            SemanticRole.UNKNOWN,
            0.15,
            "insufficient_semantic_evidence",
            (f"kind={geometry.kind.value}",),
        )

    def build_site_context(self, service: SiteModelService) -> SiteContext:
        snapshot = service.snapshot()
        resolved_roles: dict[str, SemanticRole] = {}
        for geometry in snapshot.geometries:
            resolved = service.resolved_annotation(geometry.geometry_id)
            if resolved is not None:
                resolved_roles[geometry.geometry_id] = resolved.role
        return SiteContextInterpreter().build(snapshot.geometries, resolved_roles=resolved_roles)

    def build_artist_feedback_rules(self, service: SiteModelService) -> tuple[ArtistFeedbackRule, ...]:
        votes: dict[str, Counter[SemanticRole]] = defaultdict(Counter)
        source_ids: dict[tuple[str, SemanticRole], list[str]] = defaultdict(list)
        for geometry in service.snapshot().geometries:
            artist = [
                item
                for item in service.annotations_for(geometry.geometry_id)
                if item.source in {AnnotationSource.ARTIST_CONFIRMED, AnnotationSource.ARTIST_OVERRIDE}
            ]
            if not artist:
                continue
            latest = max(artist, key=lambda item: item.revision)
            signature = self.geometry_signature(geometry)
            metadata = geometry.metadata
            # Feedback is reusable only when it has a meaningful source signature.
            # A generic closed region/line signature is too broad and can leak a
            # building correction into unrelated driveway, lawn, or planting areas.
            if not str(metadata.get("source_layer") or "").strip() and not str(metadata.get("semantic_hint") or "").strip():
                continue
            votes[signature][latest.role] += 1
            source_ids[(signature, latest.role)].append(geometry.geometry_id)

        rules: list[ArtistFeedbackRule] = []
        for signature, counts in sorted(votes.items()):
            role, count = counts.most_common(1)[0]
            rules.append(ArtistFeedbackRule(signature, role, count, tuple(sorted(source_ids[(signature, role)]))))
        return tuple(rules)

    @staticmethod
    def geometry_signature(geometry: SiteGeometry) -> str:
        metadata = geometry.metadata
        layer = str(metadata.get("source_layer") or "").strip().lower()
        source_kind = str(metadata.get("project_source_kind") or "").strip().lower()
        return f"{source_kind}|{layer}|{geometry.kind.value}|closed={int(bool(geometry.closed))}"

    @staticmethod
    def _semantic_text(geometry: SiteGeometry) -> str:
        metadata = geometry.metadata
        values = [
            str(metadata.get("source_layer") or ""),
            str(metadata.get("label") or ""),
            str(metadata.get("name") or ""),
            str(metadata.get("semantic_hint") or ""),
            str(metadata.get("project_source_path") or ""),
        ]
        return " ".join(values).replace("-", " ").replace("_", " ").lower()
