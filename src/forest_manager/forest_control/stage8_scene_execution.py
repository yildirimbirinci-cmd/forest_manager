from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
from typing import Any

from forest_manager.max_bridge.runtime_bridge import (
    get_single_forest_distribution_diagnostics,
    read_plant_group_manifest,
    write_plant_group_manifest,
)
from forest_manager.site_model import PlantingPlan
from forest_manager.site_model.pre_scene_readiness import assess_plan_pre_scene_readiness

from .plant_group_execution import execute_plant_group_manifest
from .stage8_asset_resolution import Stage8T2AssetResolver
from .planting_plan_service import Forest01FoundationService
from .service import ForestControlError, ForestPackControlService
from .execution_lineage import ExecutionLineageError, build_execution_lineage
from .resolution_pipeline_gate import ResolutionPipelineGateError, validate_resolution_pipeline
from .scene_execution_recovery import rollback_geometry_tail_to_count, verify_recovered_scene_state


_ROLE_SPACING_FACTORS = {
    "foreground_mass": 0.08,
    "mid_accent": 0.10,
    "structural_shrub": 0.18,
}

_GROWTH_FORM_SPACING_FACTORS = {
    "groundcover": 0.055,
    "grass": 0.075,
    "perennial": 0.085,
    "bulb": 0.075,
    "shrub": 0.16,
    "tree": 0.26,
    "climber": 0.12,
    "unknown": 0.10,
}


class Stage8SceneExecutionError(RuntimeError):
    pass


def _is_missing_forest_manifest_storage_error(exc: Exception) -> bool:
    """Return True only for the bridge's explicit no-FM_Forest_001 manifest case.

    A clean Stage 8 scene legitimately has no Forest object yet, so there is no
    plant-group manifest storage to snapshot.  That state is an empty baseline,
    not a recovery failure.  Every other manifest read failure remains fail-closed.
    """
    message = str(exc or "")
    return (
        "FM_PLANT_GROUP_MANIFEST_GET" in message
        and "FM_Forest_001 is required for plant-group manifest storage" in message
    )


def _snapshot_existing_plant_group_manifest() -> tuple[dict[str, Any], bool]:
    """Snapshot the current manifest without rejecting a clean pre-Forest scene.

    Returns ``(manifest, present)``.  A missing FM_Forest_001 object is represented
    as an empty manifest with ``present=False`` so ensure_forest() may perform the
    first managed bootstrap.  Transport/bridge/parse failures are still fatal.
    """
    try:
        value = read_plant_group_manifest()
    except Exception as exc:
        if _is_missing_forest_manifest_storage_error(exc):
            return {}, False
        raise Stage8SceneExecutionError(
            "Could not snapshot the existing plant-group manifest before scene mutation: " + str(exc)
        ) from exc
    return (dict(value) if isinstance(value, dict) else {}, bool(value))


@dataclass(frozen=True)
class Stage8PreparedFileEvidence:
    group_id: str
    kind: str
    path: str
    size: int
    mtime_ns: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "kind": self.kind,
            "path": self.path,
            "size": self.size,
            "mtime_ns": self.mtime_ns,
        }


def _capture_prepared_file_evidence(plan: PlantingPlan) -> tuple[Stage8PreparedFileEvidence, ...]:
    """Snapshot exact asset and mask inputs without hashing multi-GB .max files.

    Prepared execution is intentionally split from scene mutation.  The files
    approved during prepare() must therefore not silently change in the gap
    before execute_prepared().  Canonical path + size + nanosecond mtime is a
    fast fail-closed identity guard suitable for large T2 assets.
    """
    evidence: list[Stage8PreparedFileEvidence] = []
    for group in plan.groups:
        for kind, raw_path in (
            ("asset", str(group.resolved_asset_path or "")),
            ("mask", str(group.zone_mask_path or "")),
        ):
            value = raw_path.strip()
            if not value:
                continue
            path = Path(value).expanduser()
            if not path.is_file():
                continue
            resolved = path.resolve()
            stat = resolved.stat()
            evidence.append(Stage8PreparedFileEvidence(
                group_id=str(group.group_id),
                kind=kind,
                path=str(resolved),
                size=int(stat.st_size),
                mtime_ns=int(stat.st_mtime_ns),
            ))
    return tuple(evidence)


def _validate_prepared_file_evidence(
    plan: PlantingPlan,
    expected: tuple[Stage8PreparedFileEvidence, ...],
) -> None:
    current = _capture_prepared_file_evidence(plan)
    expected_map = {(item.group_id, item.kind): item for item in expected}
    current_map = {(item.group_id, item.kind): item for item in current}

    required_keys: set[tuple[str, str]] = set()
    for group in plan.groups:
        if str(group.resolved_asset_path or "").strip():
            required_keys.add((str(group.group_id), "asset"))
        if str(group.zone_mask_path or "").strip():
            required_keys.add((str(group.group_id), "mask"))

    missing_snapshot = sorted(required_keys - set(expected_map))
    missing_current = sorted(required_keys - set(current_map))
    if missing_snapshot or missing_current:
        raise Stage8SceneExecutionError(
            "Prepared Stage 8 file evidence is incomplete before scene mutation: "
            f"missing_snapshot={missing_snapshot} missing_current={missing_current}"
        )

    for key in sorted(required_keys):
        before = expected_map[key]
        after = current_map[key]
        if (before.path, before.size, before.mtime_ns) != (after.path, after.size, after.mtime_ns):
            raise Stage8SceneExecutionError(
                "Prepared Stage 8 input changed after approval and before scene mutation: "
                f"group={before.group_id} kind={before.kind} path={before.path}"
            )


def _prepared_plan_fingerprint(plan: PlantingPlan) -> str:
    """Return a stable digest of the exact logical plan approved by prepare().

    File evidence protects on-disk inputs. This digest protects the in-memory
    execution contract itself so a prepared plan cannot be altered between the
    side-effect-free approval phase and scene mutation.
    """
    boundary = plan.site_model.primary_boundary
    payload = {
        "forest_name": str(plan.forest_name),
        "reference_image_path": str(plan.reference_image_path or ""),
        "generated_by": str(plan.generated_by or ""),
        "boundary": {
            "node_name": str(boundary.node_name),
            "width_system_units": float(boundary.width_system_units),
            "depth_system_units": float(boundary.depth_system_units),
        },
        "groups": [
            {
                "group_id": str(group.group_id),
                "label": str(group.label),
                "order": int(group.order),
                "semantic_role": str(group.semantic_role),
                "coverage_weight": float(group.coverage_weight),
                "source_names": [str(value) for value in group.source_names],
                "zone_mask_path": str(group.zone_mask_path or ""),
                "resolved_asset_path": str(group.resolved_asset_path or ""),
                "model_match_confidence": float(group.model_match_confidence),
                "model_retrieval_score": float(getattr(group, "model_retrieval_score", 0.0) or 0.0),
                "scientific_name_hint": str(group.scientific_name_hint or ""),
                "common_name_hint": str(group.common_name_hint or ""),
                "growth_form": str(group.growth_form or ""),
                "flower_color": str(group.flower_color or ""),
                "foliage_color": str(group.foliage_color or ""),
                "visual_features": [str(value) for value in group.visual_features],
            }
            for group in plan.groups
        ],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _validate_prepared_plan_fingerprint(plan: PlantingPlan, expected: str) -> None:
    current = _prepared_plan_fingerprint(plan)
    if not expected or current != expected:
        raise Stage8SceneExecutionError(
            "Prepared Stage 8 plan changed after approval and before scene mutation; "
            f"expected_fingerprint={expected or '<missing>'} current_fingerprint={current}"
        )


@dataclass(frozen=True)
class Stage8PreparedScenePlan:
    """Side-effect-free Stage 8 resolution result prepared before scene mutation.

    resolved_plan is the complete observation plan and deliberately retains
    excluded/generic observations for diagnostics and later artist review.
    execution_plan is a derived, normalized scene contract containing only
    groups that are both execution-required and verified by T2 resolution.
    """

    resolved_plan: PlantingPlan
    execution_plan: PlantingPlan
    ai_asset_resolution: tuple[dict[str, Any], ...]
    resolution_pipeline_gate: Any
    pre_scene_readiness: Any
    file_evidence: tuple[Stage8PreparedFileEvidence, ...]
    plan_fingerprint: str
    execution_plan_fingerprint: str

    @property
    def ready(self) -> bool:
        return bool(
            self.resolution_pipeline_gate.ready
            and self.pre_scene_readiness.ready
            and self.execution_plan.groups
        )

    def to_dict(self) -> dict[str, Any]:
        execution_ids = [str(group.group_id) for group in self.execution_plan.groups]
        full_ids = [str(group.group_id) for group in self.resolved_plan.groups]
        execution_set = set(execution_ids)
        return {
            "ready": self.ready,
            "resolution_pipeline_gate": self.resolution_pipeline_gate.to_dict(),
            "pre_scene_readiness": self.pre_scene_readiness.to_dict(),
            "ai_asset_resolution": list(self.ai_asset_resolution),
            "full_plan_group_count": len(full_ids),
            "execution_group_count": len(execution_ids),
            "execution_group_ids": execution_ids,
            "excluded_observation_ids": [value for value in full_ids if value not in execution_set],
            "execution_coverage_total": round(
                sum(float(group.coverage_weight) for group in self.execution_plan.groups), 8
            ),
            "file_evidence": [item.to_dict() for item in self.file_evidence],
            "plan_fingerprint": self.plan_fingerprint,
            "execution_plan_fingerprint": self.execution_plan_fingerprint,
        }


def _build_verified_execution_plan(
    plan: PlantingPlan,
    resolution_gate: Any,
    pre_scene_readiness: Any,
) -> PlantingPlan:
    """Derive the only plan that is allowed to mutate the 3ds Max scene.

    The full resolved plan remains untouched.  Scene execution receives only
    groups that are BOTH required by the identity gate and verified by the T2
    resolution gate.  Coverage is renormalized across that executable subset so
    excluded observations never create holes or distort Forest distribution.
    """
    required_ids = {str(value) for value in (pre_scene_readiness.required_group_ids or ())}
    verified_ids = {str(value) for value in (resolution_gate.verified_group_ids or ())}
    execution_ids = required_ids & verified_ids

    selected = tuple(group for group in plan.groups if str(group.group_id) in execution_ids)
    if not selected:
        return replace(plan, groups=())

    coverage_total = sum(max(0.0, float(group.coverage_weight)) for group in selected)
    if coverage_total <= 0.0:
        raise Stage8SceneExecutionError(
            "Verified Stage 8 execution groups have no positive coverage weight."
        )

    normalized = tuple(
        replace(
            group,
            coverage_weight=max(0.0, float(group.coverage_weight)) / coverage_total,
        )
        for group in selected
    )
    return replace(plan, groups=normalized)


def _geometry_source_names(service: ForestPackControlService, forest_name: str) -> list[str]:
    inventory = service.inventory(forest_name, preflight=False)
    prop = next(
        (
            item
            for item in inventory.get("properties") or []
            if isinstance(item, dict) and str(item.get("name") or "").lower() == "cobjlist"
        ),
        None,
    )
    metadata = prop.get("array_metadata") if isinstance(prop, dict) else None
    count = int((metadata or {}).get("count") or 0) if isinstance(metadata, dict) else 0
    names: list[str] = []
    for index in range(count):
        row = service.get_array_element(forest_name, "cobjlist", index, preflight=False)
        value = str(row.get("value") or "").strip()
        if value:
            names.append(value)
    return names


def _ensure_required_geometry_sources(
    service: ForestPackControlService,
    forest_name: str,
    plan: PlantingPlan,
    *,
    asset_resolver: Stage8T2AssetResolver,
) -> tuple[dict[str, Any], PlantingPlan]:
    existing = _geometry_source_names(service, forest_name)
    added: list[dict[str, Any]] = []
    merged: list[dict[str, Any]] = []
    source_name_map: dict[str, str] = {}

    for group in plan.groups:
        for requested_name in group.source_names:
            if requested_name in existing:
                source_name_map[requested_name] = requested_name
                continue

            # First reuse a scene node if the source already exists outside the
            # Forest Geometry List. A clean Stage 8 scene normally falls through
            # to the T2 merge path below.
            try:
                result = service.add_geometry_source_by_name(forest_name, requested_name, preflight=False)
            except ForestControlError as exc:
                if "Source geometry node not found" not in str(exc):
                    raise
            else:
                added.append(result)
                existing = _geometry_source_names(service, forest_name)
                if requested_name not in existing:
                    raise Stage8SceneExecutionError(
                        f"Existing scene source '{requested_name}' was added but did not verify in the Geometry List."
                    )
                source_name_map[requested_name] = requested_name
                continue

            merge_result = asset_resolver.merge_missing_source(
                requested_name,
                group.semantic_role,
                geometry_count=len(existing),
                exact_asset_path=group.resolved_asset_path or None,
            )
            actual_name = str(merge_result.get("source_name") or "").strip()
            if not actual_name:
                raise Stage8SceneExecutionError(f"T2 merge returned no source node for '{requested_name}'.")
            merged.append(merge_result)
            source_name_map[requested_name] = actual_name
            existing = _geometry_source_names(service, forest_name)
            if actual_name not in existing:
                raise Stage8SceneExecutionError(
                    f"T2 asset '{requested_name}' merged as '{actual_name}' but was not present in the Forest Geometry List."
                )

    effective_plan = asset_resolver.remap_plan(plan, source_name_map)
    required = [name for group in effective_plan.groups for name in group.source_names]
    missing = [name for name in required if name not in existing]
    if missing:
        raise Stage8SceneExecutionError(
            "Required Stage 8 species could not be bound to the Forest Geometry List: " + ", ".join(missing)
        )
    return ({
        "required": required,
        "existing_after": existing,
        "added_from_scene": added,
        "merged_from_t2": merged,
        "source_name_map": source_name_map,
        "verified": not missing,
    }, effective_plan)


def _scene_spacing_system(plan: PlantingPlan, semantic_role: str, growth_form: str = "unknown") -> float:
    boundary = plan.site_model.primary_boundary
    extent = min(float(boundary.width_system_units), float(boundary.depth_system_units))
    if extent <= 0.0:
        extent = max(float(boundary.width_system_units), float(boundary.depth_system_units), 100.0)
    normalized_growth = str(growth_form or "unknown").strip().lower()
    factor = float(_GROWTH_FORM_SPACING_FACTORS.get(normalized_growth, _ROLE_SPACING_FACTORS.get(semantic_role, 0.10)))
    # Keep the initial Stage 8 plan proportional to the actual site.  This is a
    # baseline only; user edits remain exact values later.
    return max(5.0, extent * factor)


def _validate_runtime_manifest_scope(plan: PlantingPlan, manifest: dict[str, Any]) -> dict[str, Any]:
    """Fail closed unless the runtime manifest is an exact projection of the verified execution plan.

    Stage 8 keeps excluded observations in the full diagnostic plan. They must
    never re-enter the Forest mutation path through manifest construction,
    remapping, or later execution helpers.
    """
    plan_groups = list(plan.groups)
    manifest_groups = [item for item in (manifest.get("groups") or []) if isinstance(item, dict)]
    plan_ids = [str(group.group_id) for group in plan_groups]
    manifest_ids = [str(item.get("group_id") or "") for item in manifest_groups]
    if not plan_ids or manifest_ids != plan_ids:
        raise Stage8SceneExecutionError(
            "Stage 8 runtime manifest scope mismatch: "
            f"execution_plan={plan_ids} manifest={manifest_ids}"
        )

    for group, item in zip(plan_groups, manifest_groups):
        expected_sources = [str(value) for value in group.source_names]
        actual_sources = [str(value) for value in (item.get("source_names") or [])]
        if actual_sources != expected_sources:
            raise Stage8SceneExecutionError(
                "Stage 8 runtime manifest source lineage mismatch for "
                f"'{group.group_id}': plan={expected_sources} manifest={actual_sources}"
            )
        if str(item.get("resolved_asset_path") or "") != str(group.resolved_asset_path or ""):
            raise Stage8SceneExecutionError(
                f"Stage 8 runtime manifest asset lineage mismatch for '{group.group_id}'."
            )
        if str(item.get("zone_mask_path") or "") != str(group.zone_mask_path or ""):
            raise Stage8SceneExecutionError(
                f"Stage 8 runtime manifest mask lineage mismatch for '{group.group_id}'."
            )
        if abs(float(item.get("coverage_weight") or 0.0) - float(group.coverage_weight)) > 1e-9:
            raise Stage8SceneExecutionError(
                f"Stage 8 runtime manifest coverage mismatch for '{group.group_id}'."
            )

    total = sum(float(item.get("coverage_weight") or 0.0) for item in manifest_groups)
    if abs(total - 1.0) > 1e-7:
        raise Stage8SceneExecutionError(
            f"Stage 8 runtime manifest execution coverage is not normalized: {total:.8f}"
        )
    return {
        "verified": True,
        "group_count": len(plan_ids),
        "group_ids": plan_ids,
        "coverage_total": round(total, 8),
    }


def plan_to_runtime_manifest(plan: PlantingPlan) -> dict[str, Any]:
    if not plan.execution_ready:
        unresolved = [group.group_id for group in plan.groups if not group.source_names]
        raise Stage8SceneExecutionError(
            "PlantingPlan is not execution-ready; unresolved groups: " + ", ".join(unresolved)
        )
    if not plan.visual_intent_ready:
        unresolved = [group.group_id for group in plan.groups if not group.zone_mask_path]
        raise Stage8SceneExecutionError(
            "PlantingPlan has no visual zone masks for: " + ", ".join(unresolved)
        )

    area_node = plan.site_model.primary_boundary.node_name
    groups: list[dict[str, Any]] = []
    for group in plan.groups:
        spacing = _scene_spacing_system(plan, group.semantic_role, group.growth_form)
        artist_values = {
            "species_enabled": True,
            "species_scale_percent": 100.0,
            "naturalness": group.naturalness,
            "cluster_character": group.cluster_character,
        }
        groups.append(
            {
                "group_id": group.group_id,
                "label": group.label,
                "order": int(group.order),
                "semantic_role": group.semantic_role,
                "source_names": list(group.source_names),
                "spacing_system": [float(spacing), float(spacing)],
                "area_nodes": [area_node],
                "area_modes": [0],
                "coverage_weight": float(group.coverage_weight),
                "zone_mask_path": str(group.zone_mask_path or ""),
                "visual_confidence": float(group.visual_confidence),
                "scientific_name_hint": group.scientific_name_hint,
                "common_name_hint": group.common_name_hint,
                "growth_form": group.growth_form,
                "flower_color": group.flower_color,
                "foliage_color": group.foliage_color,
                "visual_features": list(group.visual_features),
                "model_match_confidence": float(group.model_match_confidence),
                "resolved_asset_path": str(group.resolved_asset_path or ""),
                "artist_values": artist_values,
                "reset_defaults": {
                    "spacing_system": [float(spacing), float(spacing)],
                    "area_reference_system": min(
                        float(plan.site_model.primary_boundary.width_system_units),
                        float(plan.site_model.primary_boundary.depth_system_units),
                    ),
                    "artist_values": dict(artist_values),
                },
            }
        )
    return {
        "schema_version": 2,
        "primary_forest": plan.forest_name,
        "generated_by": plan.generated_by,
        "reference_image_path": plan.reference_image_path,
        "site_boundary": asdict(plan.site_model.primary_boundary),
        "groups": groups,
    }



class Stage8PlantingPlanSceneExecutor:
    def __init__(
        self,
        service: ForestPackControlService | None = None,
        asset_resolver: Stage8T2AssetResolver | None = None,
    ) -> None:
        self.service = service or ForestPackControlService()
        self.foundation = Forest01FoundationService()
        self.asset_resolver = asset_resolver or Stage8T2AssetResolver()
        self.last_recovery_report: dict[str, Any] | None = None

    def prepare(self, plan: PlantingPlan) -> Stage8PreparedScenePlan:
        """Resolve T2 assets and validate all pre-scene gates without mutating 3ds Max."""
        if not plan.visual_intent_ready:
            raise Stage8SceneExecutionError("Stage 8 PlantingPlan has no visual zone masks for scene execution.")

        resolved_plan, ai_asset_resolution = self.asset_resolver.resolve_plan_sources_diagnostic(plan)
        try:
            resolution_gate = validate_resolution_pipeline(resolved_plan, ai_asset_resolution)
        except ResolutionPipelineGateError as exc:
            raise Stage8SceneExecutionError(
                "Stage 8 T2 resolution lineage failed before scene mutation: " + str(exc)
            ) from exc
        pre_scene_readiness = assess_plan_pre_scene_readiness(resolved_plan, ai_asset_resolution)
        execution_plan = _build_verified_execution_plan(
            resolved_plan,
            resolution_gate,
            pre_scene_readiness,
        )
        # Only files that can actually mutate the scene are execution inputs.
        # Excluded observations remain preserved in resolved_plan for diagnostics.
        file_evidence = _capture_prepared_file_evidence(execution_plan)
        plan_fingerprint = _prepared_plan_fingerprint(resolved_plan)
        execution_plan_fingerprint = _prepared_plan_fingerprint(execution_plan)
        return Stage8PreparedScenePlan(
            resolved_plan=resolved_plan,
            execution_plan=execution_plan,
            ai_asset_resolution=tuple(ai_asset_resolution),
            resolution_pipeline_gate=resolution_gate,
            pre_scene_readiness=pre_scene_readiness,
            file_evidence=file_evidence,
            plan_fingerprint=plan_fingerprint,
            execution_plan_fingerprint=execution_plan_fingerprint,
        )

    def validate_prepared_for_execution(self, prepared: Stage8PreparedScenePlan) -> dict[str, Any]:
        """Revalidate an already-prepared plan without mutating the 3ds Max scene."""
        resolved_plan = prepared.resolved_plan
        execution_plan = prepared.execution_plan
        ai_asset_resolution = list(prepared.ai_asset_resolution)

        # Preserve the complete observation plan AND the exact derived execution
        # contract between prepare() and execute_prepared().  Only execution-plan
        # files are scene inputs, so excluded observations cannot leak into Max.
        _validate_prepared_plan_fingerprint(resolved_plan, prepared.plan_fingerprint)
        _validate_prepared_plan_fingerprint(execution_plan, prepared.execution_plan_fingerprint)
        _validate_prepared_file_evidence(execution_plan, prepared.file_evidence)

        try:
            resolution_gate = validate_resolution_pipeline(resolved_plan, ai_asset_resolution)
        except ResolutionPipelineGateError as exc:
            raise Stage8SceneExecutionError(
                "Prepared Stage 8 T2 resolution lineage failed before scene mutation: " + str(exc)
            ) from exc
        pre_scene_readiness = assess_plan_pre_scene_readiness(resolved_plan, ai_asset_resolution)
        current_execution_plan = _build_verified_execution_plan(
            resolved_plan,
            resolution_gate,
            pre_scene_readiness,
        )
        _validate_prepared_plan_fingerprint(
            current_execution_plan,
            prepared.execution_plan_fingerprint,
        )
        if not resolution_gate.ready or not pre_scene_readiness.ready:
            blocked = [
                f"{group.group_id}: {', '.join(group.blockers)}"
                for group in pre_scene_readiness.groups
                if not group.ready and group.required_for_execution
            ]
            detail = "; ".join(blocked) or str(resolution_gate.to_dict())
            raise Stage8SceneExecutionError(
                "Stage 8 prepared plan is not scene-ready; no scene mutation was allowed. " + detail
            )

        validation = self.foundation.validate_plan(execution_plan)
        if not validation.get("execution_ready") or not validation.get("visual_intent_ready"):
            raise Stage8SceneExecutionError("AI-resolved Stage 8 PlantingPlan is not ready for scene execution.")
        return {
            "ready": True,
            "execution_group_count": len(execution_plan.groups),
            "resolution_pipeline_gate": resolution_gate.to_dict(),
            "pre_scene_readiness": pre_scene_readiness.to_dict(),
            "foundation_validation": dict(validation),
        }

    def execute_prepared(self, prepared: Stage8PreparedScenePlan) -> dict[str, Any]:
        """Execute an already-resolved plan with exact failure recovery."""
        execution_plan = prepared.execution_plan
        ai_asset_resolution = list(prepared.ai_asset_resolution)

        # Keep the same mutation boundary used by final runtime acceptance: every
        # integrity/readiness check is completed before ensure_forest() can touch Max.
        validation_detail = self.validate_prepared_for_execution(prepared)

        previous_manifest, previous_manifest_present = _snapshot_existing_plant_group_manifest()

        forest_result = self.foundation.ensure_forest(execution_plan.site_model)
        if not forest_result.get("verified"):
            raise Stage8SceneExecutionError("Primary Forest bootstrap did not verify.")

        geometry_baseline = _geometry_source_names(self.service, execution_plan.forest_name)
        self.last_recovery_report = None

        try:
            geometry_result, effective_plan = _ensure_required_geometry_sources(
                self.service,
                execution_plan.forest_name,
                execution_plan,
                asset_resolver=self.asset_resolver,
            )
            manifest = plan_to_runtime_manifest(effective_plan)
            manifest_scope = _validate_runtime_manifest_scope(effective_plan, manifest)

            execution = execute_plant_group_manifest(manifest, service=self.service, strict_acceptance=True)
            if not execution.get("verified"):
                raise Stage8SceneExecutionError("PlantingPlan Forest execution did not verify.")

            manifest_write = write_plant_group_manifest(manifest)
            diagnostics = get_single_forest_distribution_diagnostics(
                execution_plan.forest_name,
                require_color_id_binding=execution.get("map_source_kind") != "disabled_map_free",
            )
            generated = {
                int(item.get("species_id") or 0): int(item.get("generated_items") or 0)
                for item in diagnostics.get("generated_geometry_ids") or []
                if isinstance(item, dict)
            }
            executed_species = [
                int(species_id)
                for group in execution.get("groups") or []
                for species_id in (group.get("species_ids") or [])
            ]
            configured_species = [int(value) for value in diagnostics.get("configured_species_ids") or []]
            missing_generated: list[int] = []
            if generated:
                missing_generated = [species_id for species_id in executed_species if generated.get(species_id, 0) <= 0]
                if missing_generated:
                    raise Stage8SceneExecutionError(
                        "Stage 8 scene execution produced no instances for species IDs: "
                        + ", ".join(str(value) for value in missing_generated)
                    )
            else:
                map_free = execution.get("map_source_kind") == "disabled_map_free"
                if not map_free and diagnostics.get("species_binding_verified") is not True:
                    raise Stage8SceneExecutionError("Stage 8 scene execution did not verify Single-Forest species bindings.")
                if int(diagnostics.get("generated_items") or 0) <= 0:
                    raise Stage8SceneExecutionError("Stage 8 scene execution generated no Forest items.")
                if set(configured_species) != set(executed_species):
                    raise Stage8SceneExecutionError(
                        "Stage 8 Single-Forest configured species mismatch: "
                        f"configured={configured_species} executed={executed_species}"
                    )
                if map_free:
                    if int(diagnostics.get("geometry_count") or 0) != len(executed_species):
                        raise Stage8SceneExecutionError(
                            "Stage 8 map-free Geometry count mismatch: "
                            f"geometry_count={diagnostics.get('geometry_count')} executed={len(executed_species)}"
                        )
                    diagnostics["verified"] = True
                    diagnostics["map_free_verified"] = True
                    diagnostics["verification_mode"] = "map_free_geometry_and_generated_items"

            try:
                execution_lineage = build_execution_lineage(
                    plan=effective_plan,
                    ai_asset_resolution=ai_asset_resolution,
                    geometry_result=geometry_result,
                    execution=execution,
                    diagnostics=diagnostics,
                    color_id_results=execution.get("color_id_results") or [],
                )
            except ExecutionLineageError as exc:
                raise Stage8SceneExecutionError(str(exc)) from exc

        except Exception as original_exc:
            recovery_report: dict[str, Any] = {}
            recovery_errors: list[str] = []
            try:
                current_geometry = _geometry_source_names(self.service, execution_plan.forest_name)
                rollback = rollback_geometry_tail_to_count(
                    execution_plan.forest_name,
                    current_count=len(current_geometry),
                    target_count=len(geometry_baseline),
                )
                recovery_report["geometry_tail"] = rollback.to_dict()
            except Exception as rollback_exc:
                recovery_errors.append(type(rollback_exc).__name__ + ": " + str(rollback_exc))
                recovery_report["geometry_tail"] = {"verified": False}

            try:
                manifest_restore = write_plant_group_manifest(
                    previous_manifest if isinstance(previous_manifest, dict) else {}
                )
                recovery_report["manifest_restore"] = manifest_restore
            except Exception as restore_exc:
                recovery_errors.append(type(restore_exc).__name__ + ": " + str(restore_exc))
                recovery_report["manifest_restore"] = {"verified": False}

            try:
                actual_geometry = _geometry_source_names(self.service, execution_plan.forest_name)
                actual_manifest = read_plant_group_manifest()
                recovered = verify_recovered_scene_state(
                    execution_plan.forest_name,
                    expected_geometry_sources=geometry_baseline,
                    actual_geometry_sources=actual_geometry,
                    expected_manifest=previous_manifest if isinstance(previous_manifest, dict) else {},
                    actual_manifest=actual_manifest if isinstance(actual_manifest, dict) else {},
                )
                recovery_report["baseline_verification"] = recovered.to_dict()
            except Exception as verify_exc:
                recovery_errors.append(type(verify_exc).__name__ + ": " + str(verify_exc))
                recovery_report["baseline_verification"] = {
                    "geometry_verified": False,
                    "manifest_verified": False,
                    "retry_safe": False,
                    "error": type(verify_exc).__name__ + ": " + str(verify_exc),
                }

            recovery_report["recovery_complete"] = not recovery_errors
            recovery_report["retry_safe"] = bool(
                recovery_report["recovery_complete"]
                and (recovery_report.get("baseline_verification") or {}).get("retry_safe") is True
            )
            self.last_recovery_report = recovery_report
            detail = json.dumps(recovery_report, ensure_ascii=True, separators=(",", ":"))
            if recovery_errors:
                raise Stage8SceneExecutionError(
                    "Stage 8 scene execution failed and recovery was incomplete. "
                    f"Original={type(original_exc).__name__}: {original_exc}; "
                    f"RecoveryErrors={' | '.join(recovery_errors)}; Recovery={detail}"
                ) from original_exc
            raise Stage8SceneExecutionError(
                "Stage 8 scene execution failed; newly appended Forest Geometry entries were rolled back "
                "and the previous manifest was restored. "
                f"Original={type(original_exc).__name__}: {original_exc}; Recovery={detail}"
            ) from original_exc

        return {
            "forest": forest_result,
            "ai_asset_resolution": ai_asset_resolution,
            "resolution_pipeline_gate": validation_detail["resolution_pipeline_gate"],
            "pre_scene_readiness": validation_detail["pre_scene_readiness"],
            "geometry": geometry_result,
            "manifest": manifest,
            "manifest_scope": manifest_scope,
            "manifest_write": manifest_write,
            "execution": execution,
            "diagnostics": diagnostics,
            "generated_species_ids": sorted(set(executed_species)),
            "missing_generated_species_ids": missing_generated,
            "execution_lineage": execution_lineage,
            "verified_group_count": len(execution_lineage),
            "full_plan_group_count": len(prepared.resolved_plan.groups),
            "execution_group_count": len(execution_plan.groups),
            "execution_group_ids": [str(group.group_id) for group in execution_plan.groups],
            "excluded_observation_ids": [
                str(group.group_id)
                for group in prepared.resolved_plan.groups
                if str(group.group_id) not in {str(item.group_id) for item in execution_plan.groups}
            ],
            "prepared_resolution_reused": True,
            "recovery_baseline": {
                "geometry_count": len(geometry_baseline),
                "previous_manifest_present": previous_manifest_present,
                "clean_scene_manifest_baseline": not previous_manifest_present,
            },
            "verified": True,
        }

    def execute(self, plan: PlantingPlan) -> dict[str, Any]:
        prepared = self.prepare(plan)
        return self.execute_prepared(prepared)
