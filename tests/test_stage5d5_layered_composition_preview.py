from forest_manager.composition.layered_composition_plan import build_layered_composition_plan


def _context():
    return {
        "forest_name": "FM_Forest_001",
        "selection_area": {"area_square_meters": 7528.88},
        "density": {"meters_x": 75.0, "meters_y": 75.0},
        "geometry": {
            "geometry_names": [
                "Lavandula angustifolia 'Hidcote' (Lavender)",
                "Butomus umbellatus (Flowering rush )",
                "Bush_Berberis",
            ],
            "probabilities": [42.8571, 28.5714, 28.5715],
        },
    }


def _transform():
    return {
        "applyscale": True,
        "applyrotation": False,
        "applytranslation": False,
        "scalexmin": 80,
        "scalexmax": 120,
        "scaleymin": 80,
        "scaleymax": 120,
        "scalezmin": 100,
        "scalezmax": 100,
        "scalelock": 1,
    }


def test_expected_layer_roles_are_deterministic():
    plan = build_layered_composition_plan(_context(), _transform())
    roles = [item["role"] for item in plan["layers"]]
    assert roles == ["foreground_mass", "mid_accent", "structural_shrub"]


def test_probabilities_are_preserved():
    plan = build_layered_composition_plan(_context(), _transform())
    values = [item["current_probability"] for item in plan["layers"]]
    assert values == [42.8571, 28.5714, 28.5715]
    assert plan["probability_total"] == 100.0
    assert plan["preserve_probabilities"] is True


def test_density_is_preserved_at_verified_baseline():
    plan = build_layered_composition_plan(_context(), _transform())
    assert plan["density_meters_x"] == 75.0
    assert plan["density_meters_y"] == 75.0
    assert plan["preserve_density"] is True


def test_native_scale_state_is_carried_forward_without_editing():
    plan = build_layered_composition_plan(_context(), _transform())
    state = plan["transform_state"]
    assert state["applyscale"] is True
    assert state["scalexmin"] == 80
    assert state["scalexmax"] == 120
    assert state["applyrotation"] is False
    assert state["applytranslation"] is False


def test_preview_is_read_only():
    plan = build_layered_composition_plan(_context(), _transform())
    assert plan["read_only"] is True
    assert plan["verified"] is True
    assert "75.0 m density" in plan["next_apply_scope"]["protected"]


def test_geometry_probability_count_mismatch_is_rejected():
    context = _context()
    context["geometry"]["probabilities"] = [100.0]
    try:
        build_layered_composition_plan(context, _transform())
    except RuntimeError as exc:
        assert "count mismatch" in str(exc).lower()
    else:
        raise AssertionError("Expected RuntimeError")
