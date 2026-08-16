from __future__ import annotations

import json

from forest_manager.forest_control.service import ForestPackControlService


def main() -> int:
    service = ForestPackControlService()
    report: dict[str, object] = {"ok": False, "verified": False}
    try:
        forest_name = "FM_Forest_001"
        property_name = "cobjlist"
        index = 0
        source_index = 1
        before = service.get_array_element(forest_name, property_name, index)
        source = service.get_array_element(forest_name, property_name, source_index, preflight=False)
        if before.get("reference_type") != "cproxy" or source.get("reference_type") != "cproxy":
            raise RuntimeError("Stage 6.8 requires verified CProxy cobjlist references.")
        before_value = before.get("value")
        target = source.get("value")
        if not isinstance(before_value, str) or not before_value:
            raise RuntimeError("Stage 6.8 requires a non-empty original CProxy reference.")
        if not isinstance(target, str) or not target:
            raise RuntimeError("Stage 6.8 requires a non-empty target CProxy reference.")
        if target == before_value:
            raise RuntimeError("Stage 6.8 requires two distinct existing CProxy references.")
        count_before = int(before.get("count") or 0)
        write = service.set_array_element(forest_name, property_name, index, target, preflight=False)
        after_write = service.get_array_element(forest_name, property_name, index, preflight=False)
        rollback = service.rollback()
        after_rollback = service.get_array_element(forest_name, property_name, index, preflight=False)
        count_after = int(after_rollback.get("count") or 0)
        verified = (
            write.get("verified") is True
            and after_write.get("value") == target
            and after_rollback.get("value") == before_value
            and count_before == count_after
            and len(rollback) == 1
        )
        report = {
            "ok": verified,
            "forest_name": forest_name,
            "property_name": property_name,
            "index": index,
            "source_index": source_index,
            "reference_type": "cproxy",
            "before": before_value,
            "target": target,
            "after_write": after_write.get("value"),
            "after_rollback": after_rollback.get("value"),
            "array_count_before": count_before,
            "array_count_after": count_after,
            "rollback_step_count": len(rollback),
            "runtime_write_endpoint": write.get("verified") is True,
            "runtime_rollback_endpoint": len(rollback) == 1,
            "policy": {
                "cproxy_reference_property_allowlist": ["cobjlist"],
                "nullable_cproxy_references": True,
                "existing_scene_cproxy_resolution": True,
                "new_proxy_creation": False,
                "array_length_preserved": count_before == count_after,
                "bridge_readback_verification": True,
                "service_readback_verification": True,
                "single_session_mixed_rollback_journal": True,
                "startup_loader_content_stable_across_build_ids": True,
                "final_state_preserved": after_rollback.get("value") == before_value,
            },
            "verified": verified,
        }
    except Exception as exc:
        try:
            service.rollback()
        except Exception:
            pass
        report = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "verified": False}
    print("Forest Manager Stage 6.8 CProxy Reference Array Write Endpoint:")
    print(json.dumps(report, indent=2, ensure_ascii=True))
    if report.get("verified") is True:
        print("Stage 6.8 CProxy reference ArrayParameter write endpoint passed.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
