from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from forest_manager.forest_control.official_planting_pipeline import OfficialStage8PlantingPipeline
from forest_manager.forest_control.runtime_manifest import MapFreeManifestPolicy, MapFreeRuntimeManifestBuilder
from forest_manager.site_model.model import PlantingGroupIntent, PlantingPlan, SiteBoundary, SiteModel


@dataclass(frozen=True)
class FakeRecord:
    name: str
    file_path: Path
    source: str = "library_scan"


class FakeResolver:
    def resolve_asset(self, requested_name, semantic_role):
        return FakeRecord(requested_name + " Resolved", Path("C:/T2") / (requested_name + ".max"))

    @staticmethod
    def remap_plan(plan, source_name_map):
        from forest_manager.forest_control.stage8_asset_resolution import Stage8T2AssetResolver
        return Stage8T2AssetResolver.remap_plan(plan, source_name_map)


class FakeFoundation:
    def validate_plan(self, plan):
        unresolved = [group.group_id for group in plan.groups if not group.source_names]
        return {
            "execution_ready": not unresolved,
            "unresolved_group_ids": unresolved,
        }


class FakeRuntime:
    def __init__(self):
        self.calls = []

    def execute_manifest(self, manifest, *, strict_acceptance=True):
        self.calls.append((manifest, strict_acceptance))
        return {"verified": True, "forest_name": manifest["primary_forest"]}


def _plan():
    site = SiteModel(
        primary_boundary=SiteBoundary(node_name="Line001", area_square_meters=81.9),
        boundaries=(SiteBoundary(node_name="Line001", area_square_meters=81.9),),
        reference_image_path="C:/ref/ref02.png",
    )
    return PlantingPlan(
        site_model=site,
        forest_name="FM_Forest_001",
        groups=(
            PlantingGroupIntent("g1", "Foreground", 1, "foreground_mass", 0.6, ("Lavender",), zone_mask_path="C:/ignored/mask1.png"),
            PlantingGroupIntent("g2", "Accent", 2, "mid_accent", 0.4, ("Allium",), zone_mask_path="C:/ignored/mask2.png"),
        ),
        reference_image_path="C:/ref/ref02.png",
        generated_by="test-ai",
    )


def test_manifest_builder_uses_scene_boundary_and_never_projects_reference_masks():
    manifest = MapFreeRuntimeManifestBuilder().build(
        _plan(),
        policy=MapFreeManifestPolicy({"g1": 7500.0, "g2": 2500.0}),
    )

    assert manifest["primary_forest"] == "FM_Forest_001"
    assert manifest["map_policy"] == "parked_not_projected_from_reference_image"
    assert [group["area_nodes"] for group in manifest["groups"]] == [["Line001"], ["Line001"]]
    assert [group["spacing_system"] for group in manifest["groups"]] == [[7500.0, 7500.0], [2500.0, 2500.0]]
    assert all("zone_mask_path" not in group for group in manifest["groups"])


def test_official_pipeline_resolves_assets_then_delegates_only_to_official_runtime():
    runtime = FakeRuntime()
    pipeline = OfficialStage8PlantingPipeline(
        resolver=FakeResolver(),
        foundation=FakeFoundation(),
        scene_runtime=runtime,
    )
    prepared = pipeline.prepare(
        _plan(),
        policy=MapFreeManifestPolicy({"g1": 7500.0, "g2": 2500.0}),
    )

    assert prepared.resolved_plan.groups[0].source_names == ("Lavender Resolved",)
    assert prepared.resolved_plan.groups[1].source_names == ("Allium Resolved",)
    assert len(prepared.asset_resolution) == 2

    result = pipeline.execute(prepared, strict_acceptance=False)
    assert result["verified"] is True
    assert len(runtime.calls) == 1
    assert runtime.calls[0][1] is False
