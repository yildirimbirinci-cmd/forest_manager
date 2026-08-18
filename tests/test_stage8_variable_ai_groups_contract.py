from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "src" / "forest_manager" / "site_model" / "reference_image.py"
PLAN = ROOT / "src" / "forest_manager" / "site_model" / "planting_plan.py"


def test_reference_image_supports_variable_external_ai_groups():
    source = REFERENCE.read_text(encoding="utf-8")
    assert "def from_group_intents(" in source
    assert "stage8-reference-image-variable-groups-v2" in source
    assert "mask_path: str | None = None" in source
    assert "source_names: tuple[str, ...] = ()" in source


def test_plan_builder_uses_ai_supplied_source_names_without_three_role_limit():
    source = PLAN.read_text(encoding="utf-8")
    assert "zone.source_names" in source
    assert "for order, zone in enumerate(analysis.zones, start=1)" in source
