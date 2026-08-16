from __future__ import annotations

from forest_manager.ui.plant_groups import discover_plant_groups, discover_primary_forest


def main() -> int:
    forests = (
        "FM_Forest_001",
        "FM_Layer_01_foreground_mass",
        "FM_Layer_02_mid_accent",
        "FM_Layer_03_structural_shrub",
        "FM_Layer_04_seasonal_accent",
        "UnrelatedForest",
    )
    groups = discover_plant_groups(forests)
    assert discover_primary_forest(forests) == "FM_Forest_001"
    assert len(groups) == 4
    assert [group.label for group in groups] == [
        "Foreground Mass",
        "Mid Accent",
        "Structural Shrub",
        "Seasonal Accent",
    ]
    assert all(not group.label.startswith("FM_Layer_") for group in groups)
    assert discover_plant_groups(("FM_Forest_001",))[0].label == "All Planting"
    print("Forest Manager Stage 7.13 dynamic Plant Groups acceptance passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
