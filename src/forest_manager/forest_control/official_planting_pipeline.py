from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from forest_manager.site_model import PlantingPlan

from .ai_plant_group_resolution import AIPlantGroupAssetResolver
from .planting_plan_service import Forest01FoundationService
from .runtime_manifest import MapFreeManifestPolicy, MapFreeRuntimeManifestBuilder
from .scene_runtime import ForestSceneRuntime
from .stage8_asset_resolution import Stage8T2AssetResolver


class OfficialStage8PipelineError(RuntimeError):
    pass




@dataclass(frozen=True)
class SceneSourcePreparation:
    forest_name: str
    existing_sources: tuple[str, ...]
    reuse_sources: tuple[str, ...]
    missing_sources: tuple[dict[str, Any], ...]

    @property
    def ready(self) -> bool:
        return not self.missing_sources


@dataclass(frozen=True)
class PreparedOfficialPlantingPlan:
    resolved_plan: PlantingPlan
    manifest: dict[str, Any]
    asset_resolution: tuple[dict[str, Any], ...]


class OfficialStage8PlantingPipeline:
    """Stable map-free Stage 8 handoff from semantic plan to scene runtime.

    Asset discovery is read-only here. Source merging remains an explicit,
    separate lifecycle operation so repeated manifest execution stays idempotent.
    """

    def __init__(
        self,
        *,
        resolver: Stage8T2AssetResolver | None = None,
        foundation: Forest01FoundationService | None = None,
        manifest_builder: MapFreeRuntimeManifestBuilder | None = None,
        scene_runtime: ForestSceneRuntime | None = None,
    ) -> None:
        self.resolver = resolver or Stage8T2AssetResolver()
        self.foundation = foundation or Forest01FoundationService()
        self.manifest_builder = manifest_builder or MapFreeRuntimeManifestBuilder()
        self.scene_runtime = scene_runtime or ForestSceneRuntime()

    def prepare(
        self,
        plan: PlantingPlan,
        *,
        policy: MapFreeManifestPolicy,
    ) -> PreparedOfficialPlantingPlan:
        validation = self.foundation.validate_plan(plan)
        if validation.get("execution_ready") is not True:
            unresolved = validation.get("unresolved_group_ids") or []
            raise OfficialStage8PipelineError(
                "PlantingPlan must contain explicit requested source names before T2 resolution: "
                + ", ".join(str(value) for value in unresolved)
            )
        source_name_map: dict[str, str] = {}
        evidence: list[dict[str, Any]] = []
        for group in plan.groups:
            for requested_name in group.source_names:
                record = self.resolver.resolve_asset(requested_name, group.semantic_role)
                resolved_name = str(record.name or "").strip()
                if not resolved_name:
                    raise OfficialStage8PipelineError(
                        f"T2 resolution returned an empty asset name for '{requested_name}'."
                    )
                source_name_map[requested_name] = resolved_name
                evidence.append(
                    {
                        "group_id": group.group_id,
                        "semantic_role": group.semantic_role,
                        "requested_name": requested_name,
                        "resolved_name": resolved_name,
                        "asset_path": str(record.file_path),
                        "catalog_source": record.source,
                    }
                )
        resolved_plan = self.resolver.remap_plan(plan, source_name_map)
        resolved_validation = self.foundation.validate_plan(resolved_plan)
        if resolved_validation.get("execution_ready") is not True:
            raise OfficialStage8PipelineError("T2-resolved PlantingPlan is not execution-ready.")
        manifest = self.manifest_builder.build(resolved_plan, policy=policy)
        return PreparedOfficialPlantingPlan(
            resolved_plan=resolved_plan,
            manifest=manifest,
            asset_resolution=tuple(evidence),
        )

    def prepare_ai_candidates(
        self,
        plan: PlantingPlan,
        *,
        policy: MapFreeManifestPolicy,
    ) -> PreparedOfficialPlantingPlan:
        """Promote only real T2 matches from AI visual species hypotheses."""
        resolution = AIPlantGroupAssetResolver(self.resolver).resolve(plan)
        validation = self.foundation.validate_plan(resolution.resolved_plan)
        if validation.get("execution_ready") is not True:
            raise OfficialStage8PipelineError("AI/T2-resolved PlantingPlan is not execution-ready.")
        manifest = self.manifest_builder.build(resolution.resolved_plan, policy=policy)
        evidence = list(resolution.evidence)
        evidence.extend(
            {
                "group_id": item.get("group_id"),
                "semantic_role": item.get("semantic_role"),
                "excluded": True,
                "reason": item.get("reason"),
                "candidate_names": list(item.get("candidates") or []),
            }
            for item in resolution.excluded_groups
        )
        return PreparedOfficialPlantingPlan(
            resolved_plan=resolution.resolved_plan,
            manifest=manifest,
            asset_resolution=tuple(evidence),
        )


    def inspect_scene_sources(
        self,
        prepared: PreparedOfficialPlantingPlan,
        *,
        preflight: bool = True,
    ) -> SceneSourcePreparation:
        """Classify resolved AI/T2 sources as reusable or missing without scene mutation."""
        forest_name = str(prepared.manifest.get("primary_forest") or "").strip()
        if not forest_name:
            raise OfficialStage8PipelineError("Prepared manifest has no primary Forest name.")

        existing = self.resolver.list_geometry_source_names(forest_name, preflight=preflight)
        existing_keys = {name.casefold(): name for name in existing}
        reuse: list[str] = []
        missing: list[dict[str, Any]] = []

        for item in prepared.asset_resolution:
            if item.get("excluded"):
                continue
            resolved_name = str(item.get("resolved_name") or "").strip()
            asset_path = str(item.get("asset_path") or "").strip()
            if not resolved_name or not asset_path:
                continue
            if resolved_name.casefold() in existing_keys:
                reuse.append(existing_keys[resolved_name.casefold()])
                continue
            missing.append({
                "group_id": item.get("group_id"),
                "semantic_role": item.get("semantic_role"),
                "requested_name": item.get("requested_name"),
                "resolved_name": resolved_name,
                "asset_path": asset_path,
            })

        return SceneSourcePreparation(
            forest_name=forest_name,
            existing_sources=tuple(existing),
            reuse_sources=tuple(reuse),
            missing_sources=tuple(missing),
        )

    def ensure_scene_sources(
        self,
        prepared: PreparedOfficialPlantingPlan,
        *,
        preflight: bool = True,
    ) -> dict[str, Any]:
        """Reuse matching sources and merge only T2 assets that are actually missing."""
        inspection = self.inspect_scene_sources(prepared, preflight=preflight)
        merged: list[dict[str, Any]] = []
        geometry_count = len(inspection.existing_sources)
        for item in inspection.missing_sources:
            result = self.resolver.merge_resolved_asset(
                asset_path=item["asset_path"],
                requested_name=str(item.get("requested_name") or item["resolved_name"]),
                semantic_role=str(item.get("semantic_role") or ""),
                geometry_count=geometry_count,
            )
            merged.append({**item, **result})
            geometry_count += 1

        final_sources = self.resolver.list_geometry_source_names(inspection.forest_name, preflight=False)
        final_keys = {name.casefold() for name in final_sources}
        required = [
            str(item.get("resolved_name") or "").strip()
            for item in prepared.asset_resolution
            if not item.get("excluded") and str(item.get("resolved_name") or "").strip()
        ]
        missing_after = [name for name in required if name.casefold() not in final_keys]
        if missing_after:
            raise OfficialStage8PipelineError(
                "Required Stage 8 T2 sources are still missing after source preparation: "
                + ", ".join(missing_after)
            )
        return {
            "verified": True,
            "forest_name": inspection.forest_name,
            "existing_sources_before": list(inspection.existing_sources),
            "reuse_sources": list(inspection.reuse_sources),
            "missing_sources_before": [dict(item) for item in inspection.missing_sources],
            "merged_sources": merged,
            "final_sources": list(final_sources),
            "merge_count": len(merged),
        }


    def execute(
        self,
        prepared: PreparedOfficialPlantingPlan,
        *,
        strict_acceptance: bool = False,
    ) -> dict[str, Any]:
        result = self.scene_runtime.execute_manifest(
            prepared.manifest,
            strict_acceptance=strict_acceptance,
        )
        return {
            "verified": bool(result.get("verified")),
            "manifest": prepared.manifest,
            "asset_resolution": list(prepared.asset_resolution),
            "execution": result,
            "map_policy": "parked_not_projected_from_reference_image",
        }
