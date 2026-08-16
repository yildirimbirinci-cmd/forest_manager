from forest_manager.forest_control import ForestControlError
from forest_manager.forest_control.semantic_api import SemanticForestControlAPI


class FakeService:
    def __init__(self):
        self.rows = {
            "seed": (123456, "Integer"),
            "mirror": (False, "BooleanClass"),
            "spdensact": (False, "BooleanClass"),
            "camdensact": (False, "BooleanClass"),
            "iconSize": (100.0, "Float"),
            "opaclevel": (0.8, "Float"),
            "collheight": (0, "Integer"),
            "geomtexid": (0, "Integer"),
            "fastopac": (False, "BooleanClass"),
            "renderid": ("id", "String"),
            "divtmap": (None, "UndefinedClass"),
            "geomtex": (None, "UndefinedClass"),
        }

    def inventory(self, forest_name):
        return {
            "properties": [
                {"name": name, "value": value, "value_class": value_class}
                for name, (value, value_class) in self.rows.items()
            ]
        }


def test_explicit_runtime_read_only_routes():
    api = SemanticForestControlAPI(FakeService())
    checks = (
        ("display", "viewport", "geomtexid"),
        ("display", "fast_opacity", "fastopac"),
        ("display", "render_identifier", "renderid"),
        ("distribution", "diversity_map_reference", "divtmap"),
        ("material", "geometry_texture_reference", "geomtex"),
    )
    assert all(api.describe(*item).route == "read_only" for item in checks)


def test_get_uses_inventory_without_get_property_endpoint():
    api = SemanticForestControlAPI(FakeService())
    result = api.get("FM_Forest_001", "distribution", "extended_distribution_controls", "seed")
    assert result["value"] == 123456
    assert result["descriptor"]["route"] == "scalar_direct"
    assert result["descriptor"]["writable"] is False


def test_set_scalar_reports_runtime_boundary_without_mutation():
    api = SemanticForestControlAPI(FakeService())
    try:
        api.set_scalar("FM_Forest_001", "distribution", "extended_distribution_controls", "seed", 123456)
    except ForestControlError as exc:
        assert "no set_property runtime endpoint" in str(exc)
    else:
        raise AssertionError("Expected runtime write boundary")
    assert api.rollback() == []
