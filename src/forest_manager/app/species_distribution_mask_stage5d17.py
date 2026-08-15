from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


LAYER_ROLES = {
    "FM_Layer_01_foreground_mass": "foreground_mass",
    "FM_Layer_02_mid_accent": "mid_accent",
    "FM_Layer_03_structural_shrub": "structural_shrub",
}


def main() -> int:
    try:
        ensure_current_bridge()
        response = send_command("GET_LAYER_DENSITY_DISTRIBUTION_CONTRACT")
    except Exception as exc:
        print("Stage 5D.17 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    if not response.get("ok"):
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 3

    data = response.get("data") or {}
    layers = data.get("layers") or []
    if len(layers) != 3:
        print("Stage 5D.17 requires three prepared species layers.")
        return 4

    plan_layers = []
    coverage_total = 0.0

    for layer in layers:
        name = layer.get("forest_name")
        role = LAYER_ROLES.get(name, "species_layer")
        probability = float(layer.get("original_probability") or 0.0)
        coverage_total += probability

        props = {
            item.get("name"): item.get("value")
            for item in (layer.get("candidate_properties") or [])
            if item.get("name")
        }

        plan_layers.append(
            {
                "forest_name": name,
                "role": role,
                "target_coverage_percent": probability,
                "density_meters_x": float(layer.get("density_meters_x") or 0.0),
                "density_meters_y": float(layer.get("density_meters_y") or 0.0),
                "distribution_contract": {
                    "densityMap": props.get("densityMap"),
                    "maxdensity": props.get("maxdensity"),
                    "problist": props.get("problist"),
                    "cloudens": props.get("cloudens"),
                },
                "mask_policy": {
                    "mask_type": "grayscale_distribution_mask",
                    "coverage_basis": "original semantic species probability",
                    "overlap_policy": "exclusive_primary_regions_with_soft_boundaries",
                    "role_bias": {
                        "foreground_mass": "largest connected planting masses",
                        "mid_accent": "smaller separated accent islands",
                        "structural_shrub": "medium-to-large structural islands",
                    }.get(role, "independent species region"),
                },
            }
        )

    plan = {
        "policy": "species_distribution_masks_v1",
        "mode": "preview",
        "read_only": True,
        "goal": (
            "Preserve the verified 75.0 m Density Units value while moving "
            "species weighting from geometry probability into independent spatial masks."
        ),
        "coverage_total_percent": round(coverage_total, 4),
        "coverage_interpretation": (
            "The 42.8571 / 28.5714 / 28.5715 semantic weights become target spatial "
            "coverage shares, not per-Forest Density Units values."
        ),
        "layers": plan_layers,
        "mask_generation_requirements": {
            "deterministic_seed": True,
            "same_area_coordinate_space": True,
            "soft_boundaries": True,
            "no_asset_remerge": True,
            "no_user_spline_edit": True,
            "active_scene_units_preserved": True,
        },
        "protected_state": {
            "density_units_meters": 75.0,
            "prepared_layers_remain_disabled": True,
            "legacy_forest_remains_active": True,
            "geometry_sources": "preserve existing CProxy nodes",
            "scale_variation": "preserve",
            "rotation": "preserve disabled",
            "translation": "preserve disabled",
        },
        "next_stage": {
            "name": "Stage 5D.18 Deterministic Mask Generator",
            "scope": (
                "generate three complementary grayscale masks in a shared coordinate space, "
                "validate target coverage numerically, but do not activate Forest layers yet"
            ),
        },
        "verified": abs(coverage_total - 100.0) <= 0.01,
    }

    print("Forest Manager Stage 5D.17 Species Distribution Mask Architecture Preview:")
    print(json.dumps({"mode": "preview", "plan": plan}, indent=2, ensure_ascii=False))

    if not plan["verified"]:
        print("Stage 5D.17 verification failed: coverage total is not 100%.")
        return 5

    print("Stage 5D.17 species distribution mask architecture preview passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
