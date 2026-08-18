from dataclasses import replace
from pathlib import Path

from forest_manager.forest_control.ai_plant_group_resolution import AIPlantGroupAssetResolver
from forest_manager.forest_control.stage8_asset_resolution import Stage8AssetResolutionError
from forest_manager.site_model import PlantingGroupIntent, PlantingPlan, SiteModel
from forest_manager.site_model.model import BoundaryRole, SiteBoundary
from forest_manager.t2_bridge.catalog import T2AssetRecord


class FakeResolver:
    def resolve_asset_strict(self, requested_name, semantic_role):
        if requested_name in {"bad candidate", "unavailable"}:
            raise Stage8AssetResolutionError("not found")
        return T2AssetRecord(
            id=1,
            name={"purple coneflower": "Rudbeckia 'Goldsturm' (Coneflower)", "Japanese maple": "Acer palmatum"}.get(requested_name, requested_name),
            file_path=Path("C:/T2") / (requested_name.replace(" ", "_") + ".max"),
            folder_path=Path("C:/T2"),
            extension=".max",
            category="Plants",
            missing=False,
            source="library_scan",
        )


def _plan():
    boundary = SiteBoundary("Line001", BoundaryRole.PLANTING_BOUNDARY, 81.9)
    site = SiteModel(primary_boundary=boundary, boundaries=(boundary,))
    return PlantingPlan(
        site_model=site,
        forest_name="FM_Forest_001",
        groups=(
            PlantingGroupIntent("g1", "Flowers", 1, "flower_accent", 0.35, ("bad candidate", "purple coneflower")),
            PlantingGroupIntent("g2", "Path", 2, "groundcover", 0.25, ()),
            PlantingGroupIntent("g3", "Tree", 3, "structural_shrub", 0.05, ("Japanese maple",)),
        ),
        generated_by="stage8-reference-image-variable-groups-v2",
    )


def test_ai_resolution_promotes_only_real_t2_matches_and_skips_unresolved_groups():
    result = AIPlantGroupAssetResolver(FakeResolver()).resolve(_plan())
    assert len(result.resolved_plan.groups) == 2
    assert result.resolved_plan.groups[0].source_names == ("Rudbeckia 'Goldsturm' (Coneflower)",)
    assert result.resolved_plan.groups[1].source_names == ("Acer palmatum",)
    assert abs(sum(g.coverage_weight for g in result.resolved_plan.groups) - 1.0) < 1e-9
    assert result.excluded_groups[0]["group_id"] == "g2"
    assert result.excluded_groups[0]["reason"] == "no_species_candidates"
    assert result.evidence[0]["requested_name"] == "purple coneflower"
