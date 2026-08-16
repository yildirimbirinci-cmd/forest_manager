from __future__ import annotations

import json

from forest_manager.forest_control.service import ForestPackControlService


PREFERRED_COLOR_PROPERTIES = ("tintcolor1", "tintcolor2")


def _changed_rgb(value) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise RuntimeError("Stage 6.2 expected an RGB color payload.")
    rgb = [float(channel) for channel in value]
    rgb[0] = rgb[0] - 1.0 if rgb[0] >= 255.0 else rgb[0] + 1.0
    return rgb


def main() -> int:
    print("Forest Manager Stage 6.2 Typed Color Write Endpoint:")
    service = ForestPackControlService()
    try:
        snapshots = service.discover()
        if not snapshots:
            raise RuntimeError("No Forest Pack objects found for Stage 6.2 runtime acceptance.")
        snapshot = next((item for item in snapshots if item.forest_name == "FM_Forest_001"), snapshots[0])
        color_properties = [
            prop for prop in snapshot.properties
            if prop.value_class == "Color" and prop.write_mode == "color" and prop.readable
        ]
        if not color_properties:
            raise RuntimeError("No verified Color property found for Stage 6.2 runtime acceptance.")
        prop = next(
            (item for preferred in PREFERRED_COLOR_PROPERTIES for item in color_properties if item.name == preferred),
            color_properties[0],
        )
        forest_name = snapshot.forest_name
        property_name = prop.name
        before = service.get_property(forest_name, property_name, preflight=False).get("value")
        target = _changed_rgb(before)
        write_result = service.set_property(forest_name, property_name, target, preflight=False)
        after_write = service.get_property(forest_name, property_name, preflight=False).get("value")
        rollback = service.rollback()
        after_rollback = service.get_property(forest_name, property_name, preflight=False).get("value")
        verified = bool(
            write_result.get("verified")
            and len(rollback) == 1
            and service._colors_match(after_write, target)
            and service._colors_match(after_rollback, before)
        )
        report = {
            "ok": True,
            "forest_name": forest_name,
            "property_name": property_name,
            "value_class": prop.value_class,
            "write_mode": prop.write_mode,
            "before": before,
            "target": target,
            "after_write": after_write,
            "after_rollback": after_rollback,
            "rollback_step_count": len(rollback),
            "runtime_write_endpoint": True,
            "runtime_rollback_endpoint": True,
            "policy": {
                "color_type": "rgb_0_255",
                "bridge_readback_verification": True,
                "service_readback_verification": True,
                "single_session_mixed_rollback_journal": True,
                "startup_loader_content_stable_across_build_ids": True,
                "final_state_preserved": service._colors_match(after_rollback, before),
            },
            "verified": verified,
        }
        if not verified:
            raise RuntimeError("Stage 6.2 typed Color write verification failed.")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print("Stage 6.2 typed Color write endpoint passed.")
        return 0
    except Exception as exc:
        try:
            service.rollback()
        except Exception:
            pass
        print(json.dumps({"ok": False, "error": type(exc).__name__ + ": " + str(exc), "verified": False}, indent=2, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
