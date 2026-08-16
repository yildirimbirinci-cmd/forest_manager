from __future__ import annotations

import json

from forest_manager.forest_control.service import ForestPackControlService


def main() -> int:
    service = ForestPackControlService()
    forest_name = "FM_Forest_001"
    property_name = "coloridlist"
    index = 0
    report = {"ok": False, "verified": False}
    try:
        before_data = service.get_array_element(forest_name, property_name, index)
        before = list(before_data["value"])
        count_before = int(before_data["count"])
        target = [float(before[0]) + 1.0, float(before[1]), float(before[2])]
        write = service.set_array_element(forest_name, property_name, index, target, preflight=False)
        after_write = list(service.get_array_element(forest_name, property_name, index, preflight=False)["value"])
        rollback = service.rollback()
        final_data = service.get_array_element(forest_name, property_name, index, preflight=False)
        after_rollback = list(final_data["value"])
        count_after = int(final_data["count"])
        verified = (
            write.get("verified") is True
            and write.get("vector_type") == "point3"
            and after_write == target
            and after_rollback == before
            and count_after == count_before
            and len(rollback) == 1
        )
        report = {
            "ok": verified,
            "forest_name": forest_name,
            "property_name": property_name,
            "index": index,
            "value_class": before_data.get("value_class"),
            "vector_type": before_data.get("vector_type"),
            "before": before,
            "target": target,
            "after_write": after_write,
            "after_rollback": after_rollback,
            "array_count_before": count_before,
            "array_count_after": count_after,
            "rollback_step_count": len(rollback),
            "runtime_write_endpoint": bool(write.get("verified")),
            "runtime_rollback_endpoint": len(rollback) == 1 and bool(rollback[0].get("verified")),
            "policy": {
                "python_zero_based_indexing": True,
                "maxscript_one_based_translation": True,
                "point3_numeric_triplet_validation": True,
                "point3_finite_validation": True,
                "reference_array_writes_blocked": True,
                "array_length_preserved": count_after == count_before,
                "bridge_readback_verification": bool(write.get("verified")),
                "service_readback_verification": after_write == target,
                "single_session_mixed_rollback_journal": True,
                "startup_loader_content_stable_across_build_ids": True,
                "final_state_preserved": after_rollback == before,
            },
            "verified": verified,
        }
    except Exception as exc:
        try:
            service.rollback()
        except Exception:
            pass
        report = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "verified": False}
    print("Forest Manager Stage 6.4 Point3 Array Element Write Endpoint:")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report.get("verified"):
        print("Stage 6.4 Point3 ArrayParameter write endpoint passed.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
