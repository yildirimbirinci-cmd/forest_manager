from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from forest_manager.site_model import PlantingPlan

from .planting_plan_service import Forest01FoundationService
from .runtime_manifest import MapFreeManifestPolicy, MapFreeRuntimeManifestBuilder
from .scene_runtime import ForestSceneRuntime
from .stage8_asset_resolution import Stage8T2AssetResolver


class OfficialStage8PipelineError(RuntimeError):
    pass


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
