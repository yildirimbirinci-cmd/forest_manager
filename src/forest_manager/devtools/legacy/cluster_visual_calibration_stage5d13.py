from __future__ import annotations

import argparse
import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


TARGET_CLUSTER_SIZE_METERS = 30.0
TARGET_ROUGHNESS_PERCENT = 25.0
TARGET_BLURRY_EDGE_PERCENT = 20.0
TARGET_NOISE_PERCENT = 5.0


def _candidate_map(response: dict) -> dict[str, object]:
    data = response.get("data") or {}
    return {
        item.get("name"): item.get("value")
        for item in (data.get("candidates") or [])
        if item.get("name")
    }


def _preview() -> int:
    mapping_response = send_command("GET_CLUSTER_PARAMETER_MAPPING")
    units_response = send_command("GET_SCENE_UNITS")
    composition_response = send_command("GET_COMPOSITION_CONTEXT")

    for response in (mapping_response, units_response, composition_response):
        if not response.get("ok"):
            print(json.dumps(response, indent=2, ensure_ascii=False))
            return 3

    props = _candidate_map(mapping_response)
    required = ("divers", "clusize", "clurough", "clunoise", "cluedge")
    missing = [name for name in required if name not in props]
    if missing:
        print("Stage 5D.13 verification failed: missing properties:", ", ".join(missing))
        return 4

    units = units_response.get("data") or {}
    composition = composition_response.get("data") or {}
    density = composition.get("density") or {}
    geometry = composition.get("geometry") or {}

    one_meter = float(units.get("one_meter_system_units") or 0.0)
    if one_meter <= 0.0:
        print("Stage 5D.13 verification failed: invalid scene unit conversion.")
        return 5

    current_size_system = float(props["clusize"])
    current_size_meters = current_size_system / one_meter
    target_size_system = TARGET_CLUSTER_SIZE_METERS * one_meter

    plan = {
        "policy": "viewport_calibrated_cluster_profile_v1",
        "read_only": True,
        "forest_name": composition.get("forest_name"),
        "diversity_mode": int(props["divers"]),
        "scene_units": {
            "display_unit": units.get("display_unit"),
            "system_type": units.get("system_type"),
            "one_meter_system_units": one_meter,
        },
        "current_cluster_parameters": {
            "size_system_units": current_size_system,
            "size_meters": current_size_meters,
            "roughness_percent": float(props["clurough"]),
            "blurry_edge_percent": float(props["cluedge"]),
            "noise_percent": float(props["clunoise"]),
        },
        "proposed_cluster_parameters": {
            "size_system_units": target_size_system,
            "size_meters": TARGET_CLUSTER_SIZE_METERS,
            "roughness_percent": TARGET_ROUGHNESS_PERCENT,
            "blurry_edge_percent": TARGET_BLURRY_EDGE_PERCENT,
            "noise_percent": TARGET_NOISE_PERCENT,
        },
        "calibration_basis": {
            "observation": "Current viewport shows clustering but still too many small fragmented planting islands.",
            "goal": "Fewer, larger and more readable planting masses with calmer edges.",
        },
        "protected_state": {
            "density_meters_x": float(density.get("meters_x") or 0.0),
            "density_meters_y": float(density.get("meters_y") or 0.0),
            "probabilities": geometry.get("probabilities") or [],
            "scale_variation": "preserve",
            "rotation": "preserve disabled",
            "translation": "preserve disabled",
        },
        "verified": True,
    }

    print("Forest Manager Stage 5D.13 Visual Cluster Calibration Preview:")
    print(json.dumps({"mode": "preview", "plan": plan}, indent=2, ensure_ascii=False))
    print("Stage 5D.13 visual calibration preview passed.")
    return 0


def _apply() -> int:
    response = send_command("APPLY_VISUAL_CLUSTER_CALIBRATION")
    print("Forest Manager Stage 5D.13 Apply Visual Cluster Calibration:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        return 6

    data = response.get("data") or {}
    expected = {
        "divers": 2,
        "cluster_size_meters": TARGET_CLUSTER_SIZE_METERS,
        "clurough": TARGET_ROUGHNESS_PERCENT,
        "cluedge": TARGET_BLURRY_EDGE_PERCENT,
        "clunoise": TARGET_NOISE_PERCENT,
    }
    for key, value in expected.items():
        if abs(float(data.get(key, -999.0)) - float(value)) > 0.001:
            print("Stage 5D.13 verification failed:", key)
            return 7

    if not data.get("verified"):
        return 8

    print("Stage 5D.13 visual cluster calibration apply passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    try:
        ensure_current_bridge()
        return _apply() if args.apply else _preview()
    except Exception as exc:
        print("Stage 5D.13 error:", type(exc).__name__ + ": " + str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
