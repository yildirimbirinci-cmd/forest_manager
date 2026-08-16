from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "transform_plan_stage5d3.py"


def _load():
    spec = importlib.util.spec_from_file_location("stage5d3", APP)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _caps():
    values = {
        "applyscale": False,
        "scalexmin": 80,
        "scalexmax": 120,
        "scaleymin": 80,
        "scaleymax": 120,
        "scalezmin": 100,
        "scalezmax": 100,
        "scalelock": 1,
        "applyrotation": False,
        "applytranslation": False,
    }
    return {
        "transform_properties": [
            {"name": key, "value": value} for key, value in values.items()
        ],
        "geometry_scale_list": [100.0, 100.0, 100.0],
    }


def _context():
    return {
        "forest_name": "FM_Forest_001",
        "density": {"meters_x": 75.0, "meters_y": 75.0},
        "geometry": {
            "geometry_names": ["A", "B", "C"],
            "probabilities": [42.8571, 28.5714, 28.5715],
        },
    }


def test_plan_is_read_only():
    plan = _load().build_plan(_context(), _caps())
    assert plan["read_only"] is True


def test_plan_preserves_runtime_native_limits():
    plan = _load().build_plan(_context(), _caps())
    proposed = plan["proposed_apply"]
    assert proposed["scalexmin"] == 80
    assert proposed["scalexmax"] == 120
    assert proposed["scaleymin"] == 80
    assert proposed["scaleymax"] == 120
    assert proposed["scalezmin"] == 100
    assert proposed["scalezmax"] == 100


def test_plan_does_not_enable_rotation_or_translation():
    proposed = _load().build_plan(_context(), _caps())["proposed_apply"]
    assert proposed["enable_rotation"] is False
    assert proposed["enable_translation"] is False


def test_density_75m_is_preserved_in_preview():
    plan = _load().build_plan(_context(), _caps())
    assert plan["density_meters_x"] == 75.0
    assert plan["density_meters_y"] == 75.0


def test_current_probabilities_are_preserved():
    plan = _load().build_plan(_context(), _caps())
    assert plan["probabilities"] == [42.8571, 28.5714, 28.5715]


def test_missing_runtime_property_is_rejected():
    module = _load()
    caps = _caps()
    caps["transform_properties"] = [
        item for item in caps["transform_properties"] if item["name"] != "scalexmin"
    ]
    try:
        module.build_plan(_context(), caps)
    except RuntimeError as exc:
        assert "scalexmin" in str(exc)
    else:
        raise AssertionError("missing property should fail")
