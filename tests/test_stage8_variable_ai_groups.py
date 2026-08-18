from pathlib import Path

from PIL import Image

from forest_manager.site_model.model import SiteBoundary, SiteModel
from forest_manager.site_model.planting_plan import PlantingPlanBuilder
from forest_manager.site_model.reference_image import ReferenceImageAnalyzer


def _image(tmp_path: Path) -> Path:
    path = tmp_path / "reference.png"
    Image.new("RGB", (32, 24), (80, 120, 60)).save(path)
    return path


def test_variable_ai_group_intents_preserve_five_groups_and_species(tmp_path):
    image = _image(tmp_path)
    intents = [
        {"semantic_role": "foreground", "label": "Foreground", "coverage_weight": 26, "source_names": ["Lavender"]},
        {"semantic_role": "midground", "label": "Midground", "coverage_weight": 80, "source_names": ["Rudbeckia"]},
        {"semantic_role": "accent", "label": "Accent", "coverage_weight": 104, "source_names": ["Allium"]},
        {"semantic_role": "flower", "label": "Flower", "coverage_weight": 87, "source_names": ["Allamanda"]},
        {"semantic_role": "background", "label": "Background", "coverage_weight": 27, "source_names": ["Rosa"]},
    ]

    analysis = ReferenceImageAnalyzer().from_group_intents(str(image), intents)

    assert len(analysis.zones) == 5
    assert abs(analysis.coverage_total - 1.0) <= 1e-9
    assert [zone.semantic_role for zone in analysis.zones] == ["foreground", "midground", "accent", "flower", "background"]
    assert [zone.source_names[0] for zone in analysis.zones] == ["Lavender", "Rudbeckia", "Allium", "Allamanda", "Rosa"]
    assert all(zone.mask_path is None for zone in analysis.zones)


def test_planting_plan_builder_carries_zone_species_without_role_lookup(tmp_path):
    image = _image(tmp_path)
    analysis = ReferenceImageAnalyzer().from_group_intents(
        str(image),
        [
            {"semantic_role": "accent", "coverage_weight": 2.0, "source_names": ["Allium"]},
            {"semantic_role": "flower", "coverage_weight": 1.0, "source_names": ["Allamanda"]},
        ],
    )
    site = SiteModel(
        primary_boundary=SiteBoundary(node_name="Line001", area_square_meters=10.0),
        boundaries=(SiteBoundary(node_name="Line001", area_square_meters=10.0),),
        reference_image_path=str(image),
    )

    plan = PlantingPlanBuilder().from_reference_image(site, analysis)

    assert len(plan.groups) == 2
    assert plan.groups[0].source_names == ("Allium",)
    assert plan.groups[1].source_names == ("Allamanda",)
    assert plan.execution_ready is True
    assert plan.visual_intent_ready is False


def test_role_source_mapping_can_override_ai_supplied_species(tmp_path):
    image = _image(tmp_path)
    analysis = ReferenceImageAnalyzer().from_group_intents(
        str(image),
        [{"semantic_role": "accent", "coverage_weight": 1.0, "source_names": ["AI Candidate"]}],
    )
    site = SiteModel(
        primary_boundary=SiteBoundary(node_name="Line001", area_square_meters=10.0),
        boundaries=(SiteBoundary(node_name="Line001", area_square_meters=10.0),),
    )
    plan = PlantingPlanBuilder().from_reference_image(
        site, analysis, source_names={"accent": ("Verified Asset",)}
    )
    assert plan.groups[0].source_names == ("Verified Asset",)
