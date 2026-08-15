from forest_manager.composition.semantic_probability_plan import build_probability_plan, observed_terms


def test_reference_terms_are_extracted_with_aliases():
    terms = observed_terms("PLANTS: lavender purple white lillies flowers shrubs plants.")
    assert terms == ["lavender", "lily", "flower", "shrub"]


def test_current_three_geometry_plan_is_not_equal_weighted():
    plan = build_probability_plan(
        "PLANTS: lavender purple white lillies flowers shrubs plants.",
        [
            "Lavandula angustifolia 'Hidcote' (Lavender)",
            "Butomus umbellatus (Flowering rush )",
            "Bush_Berberis",
        ],
    )
    assert plan["probabilities"] == [42.8571, 28.5714, 28.5715]
    assert plan["probability_total"] == 100.0


def test_specific_term_outweighs_generic_category():
    plan = build_probability_plan(
        "lavender flowers shrubs",
        ["Lavandula Lavender", "Flowering plant", "Bush_Berberis"],
    )
    assert plan["items"][0]["raw_weight"] == 3.0
    assert plan["items"][1]["raw_weight"] == 2.0
    assert plan["items"][2]["raw_weight"] == 2.0


def test_unmatched_geometry_is_preserved_with_small_fallback_weight():
    plan = build_probability_plan("lavender", ["Lavandula", "UnknownPlant"])
    assert plan["items"][1]["matched_term"] is None
    assert plan["items"][1]["raw_weight"] == 0.5
    assert plan["probabilities"][1] > 0.0


def test_plan_never_changes_density():
    # The pure planner has no density input or output contract.
    plan = build_probability_plan("lavender shrub", ["Lavender", "Bush"])
    assert "density" not in plan
