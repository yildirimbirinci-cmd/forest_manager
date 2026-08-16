from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "cluster_parameter_plan_stage5d11.py"


def source() -> str:
    return APP.read_text(encoding="utf-8")


def test_preview_is_read_only():
    s = source()
    assert '"read_only": True' in s
    assert 'send_command("GET_CLUSTER_PARAMETER_MAPPING")' in s
    assert 'send_command("GET_SCENE_UNITS")' in s
    assert 'send_command("GET_COMPOSITION_CONTEXT")' in s
    assert "APPLY_" not in s
    assert "SET_" not in s


def test_profile_values_are_explicit():
    s = source()
    assert "TARGET_ROUGHNESS_PERCENT = 35.0" in s
    assert "TARGET_BLURRY_EDGE_PERCENT = 25.0" in s
    assert "TARGET_NOISE_PERCENT = 10.0" in s


def test_cluster_size_is_preserved():
    s = source()
    assert '"size_system_units": current_size_system' in s
    assert '"size_meters": current_size_meters' in s


def test_scene_units_are_used_for_size_conversion():
    s = source()
    assert 'one_meter = float(units.get("one_meter_system_units") or 0.0)' in s
    assert "current_size_meters = current_size_system / one_meter" in s


def test_density_and_probabilities_are_protected():
    s = source()
    assert '"75.0 m density"' in s
    assert '"geometry probabilities"' in s


def test_next_apply_does_not_change_cluster_size_or_mode():
    s = source()
    assert '"divers = 2"' in s
    assert '"clusize current value"' in s
