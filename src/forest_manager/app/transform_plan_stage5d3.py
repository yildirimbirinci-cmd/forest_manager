from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


_REQUIRED = (
    "applyscale",
    "scalexmin",
    "scalexmax",
    "scaleymin",
    "scaleymax",
    "scalezmin",
    "scalezmax",
    "scalelock",
    "applyrotation",
    "applytranslation",
)


def _property_map(payload: dict) -> dict[str, object]:
    result: dict[str, object] = {}
    for item in payload.get("transform_properties") or []:
        name = str(item.get("name") or "").lower()
        if name:
            result[name] = item.get("value")
    return result


def build_plan(context: dict, capabilities: dict) -> dict:
    props = _property_map(capabilities)
    missing = [name for name in _REQUIRED if name not in props]
    if missing:
        raise RuntimeError("Missing Forest transform properties: " + ", ".join(missing))

    density = context.get("density") or {}
    geometry = context.get("geometry") or {}

    return {
        "policy": "preserve_native_transform_defaults_v1",
        "read_only": True,
        "forest_name": context.get("forest_name"),
        "density_meters_x": density.get("meters_x"),
        "density_meters_y": density.get("meters_y"),
        "probabilities": geometry.get("probabilities") or [],
        "geometry_names": geometry.get("geometry_names") or [],
        "current_transform_state": {
            "applyscale": props["applyscale"],
            "scalexmin": props["scalexmin"],
            "scalexmax": props["scalexmax"],
            "scaleymin": props["scaleymin"],
            "scaleymax": props["scaleymax"],
            "scalezmin": props["scalezmin"],
            "scalezmax": props["scalezmax"],
            "scalelock": props["scalelock"],
            "applyrotation": props["applyrotation"],
            "applytranslation": props["applytranslation"],
        },
        "geometry_scale_list": capabilities.get("geometry_scale_list") or [],
        "proposed_apply": {
            "enable_scale": True,
            "preserve_existing_native_scale_limits": True,
            "scalexmin": props["scalexmin"],
            "scalexmax": props["scalexmax"],
            "scaleymin": props["scaleymin"],
            "scaleymax": props["scaleymax"],
            "scalezmin": props["scalezmin"],
            "scalezmax": props["scalezmax"],
            "scalelock": props["scalelock"],
            "enable_rotation": False,
            "enable_translation": False,
        },
        "verified": True,
    }


def main() -> int:
    try:
        ensure_current_bridge()
        context_response = send_command("GET_COMPOSITION_CONTEXT")
        capability_response = send_command("GET_TRANSFORM_CAPABILITIES")
    except Exception as exc:
        print("Stage 5D.3 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    if not context_response.get("ok"):
        print(json.dumps(context_response, indent=2, ensure_ascii=False))
        return 3
    if not capability_response.get("ok"):
        print(json.dumps(capability_response, indent=2, ensure_ascii=False))
        return 4

    try:
        plan = build_plan(
            context_response.get("data") or {},
            capability_response.get("data") or {},
        )
    except Exception as exc:
        print("Stage 5D.3 error:", type(exc).__name__ + ": " + str(exc))
        return 5

    print("Forest Manager Stage 5D.3 Transform Plan Preview:")
    print(json.dumps({"mode": "preview", "plan": plan}, indent=2, ensure_ascii=False))

    if not plan.get("read_only") or not plan.get("verified"):
        return 6
    if float(plan.get("density_meters_x") or 0.0) != 75.0:
        print("Stage 5D.3 verification failed: density X changed from 75.0 m.")
        return 7
    if float(plan.get("density_meters_y") or 0.0) != 75.0:
        print("Stage 5D.3 verification failed: density Y changed from 75.0 m.")
        return 8

    print("Stage 5D.3 transform plan preview passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
