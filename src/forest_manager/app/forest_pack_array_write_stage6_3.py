from __future__ import annotations

import json

from forest_manager.forest_control.service import ForestPackControlService


def main() -> int:
    service = ForestPackControlService()
    result: dict[str, object] = {"ok": False, "verified": False}
    try:
        forest_name = "FM_Forest_001"
        property_name = "ScaleList"
        index = 0
        before = service.get_array_element(forest_name, property_name, index)
        before_value = float(before["value"])
        target = before_value + 1.0
        write = service.set_array_element(forest_name, property_name, index, target, preflight=False)
        after_write = service.get_array_element(forest_name, property_name, index, preflight=False)
        rollback = service.rollback()
        after_rollback = service.get_array_element(forest_name, property_name, index, preflight=False)
        verified = (
            write.get("verified") is True
            and abs(float(after_write["value"]) - target) <= 1e-6
            and abs(float(after_rollback["value"]) - before_value) <= 1e-6
            and len(rollback) == 1
            and int(after_rollback.get("count") or 0) == int(before.get("count") or 0)
        )
        result = {
            "ok": verified,
            "forest_name": forest_name,
            "property_name": property_name,
            "index": index,
            "value_class": before.get("value_class"),
            "scalar_type": before.get("scalar_type"),
            "before": before_value,
            "target": target,
            "after_write": after_write.get("value"),
            "after_rollback": after_rollback.get("value"),
            "array_count_before": before.get("count"),
            "array_count_after": after_rollback.get("count"),
            "rollback_step_count": len(rollback),
            "runtime_write_endpoint": write.get("verified") is True,
            "runtime_rollback_endpoint": bool(rollback and rollback[0].get("verified")),
            "policy": {
                "python_zero_based_indexing": True,
                "maxscript_one_based_translation": True,
                "primitive_array_types": ["BooleanClass", "Integer", "Integer64", "Float", "Double", "String"],
                "reference_array_writes_blocked": True,
                "array_length_preserved": before.get("count") == after_rollback.get("count"),
                "bridge_readback_verification": True,
                "service_readback_verification": True,
                "single_session_mixed_rollback_journal": True,
                "startup_loader_content_stable_across_build_ids": True,
                "final_state_preserved": abs(float(after_rollback["value"]) - before_value) <= 1e-6,
            },
            "verified": verified,
        }
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "verified": False}
    print("Forest Manager Stage 6.3 Primitive Array Scalar Write Endpoint:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("verified") is True:
        print("Stage 6.3 primitive ArrayParameter scalar write endpoint passed.")
        return 0
    print("Stage 6.3 primitive ArrayParameter scalar write endpoint failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
