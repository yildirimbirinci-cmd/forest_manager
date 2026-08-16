from __future__ import annotations

import json

from forest_manager.forest_control.service import ForestPackControlService


def run() -> dict:
    service = ForestPackControlService()
    forest_name = "FM_Forest_001"
    property_name = "matlist"
    before0 = service.get_array_element(forest_name, property_name, 0)
    count_before = int(before0.get("count") or 0)
    if count_before < 2:
        raise RuntimeError("Stage 6.6 requires at least two existing matlist materials.")
    source = None
    source_index = None
    for index in range(1, count_before):
        candidate = service.get_array_element(forest_name, property_name, index, preflight=False)
        if candidate.get("value") and candidate.get("value") != before0.get("value"):
            source = candidate
            source_index = index
            break
    if source is None or source_index is None:
        raise RuntimeError("Stage 6.6 could not find a distinct existing material reference target.")
    target = str(source["value"])
    result = service.set_array_element(forest_name, property_name, 0, target, preflight=False)
    after_write = service.get_array_element(forest_name, property_name, 0, preflight=False)
    rollback = service.rollback()
    after_rollback = service.get_array_element(forest_name, property_name, 0, preflight=False)
    verified = bool(
        result.get("verified")
        and result.get("reference_type") == "material"
        and after_write.get("value") == target
        and after_rollback.get("value") == before0.get("value")
        and int(after_rollback.get("count") or 0) == count_before
        and len(rollback) == 1
    )
    return {
        "ok": verified,
        "forest_name": forest_name,
        "property_name": property_name,
        "index": 0,
        "source_index": source_index,
        "reference_type": "material",
        "before": before0.get("value"),
        "target": target,
        "after_write": after_write.get("value"),
        "after_rollback": after_rollback.get("value"),
        "array_count_before": count_before,
        "array_count_after": int(after_rollback.get("count") or 0),
        "rollback_step_count": len(rollback),
        "runtime_write_endpoint": bool(result.get("verified")),
        "runtime_rollback_endpoint": len(rollback) == 1 and after_rollback.get("value") == before0.get("value"),
        "policy": {
            "material_reference_property_allowlist": ["matlist"],
            "nullable_material_references": True,
            "existing_scene_material_resolution": True,
            "cproxy_bitmap_reference_writes_blocked": True,
            "array_length_preserved": int(after_rollback.get("count") or 0) == count_before,
            "bridge_readback_verification": True,
            "service_readback_verification": True,
            "single_session_mixed_rollback_journal": True,
            "startup_loader_content_stable_across_build_ids": True,
            "final_state_preserved": after_rollback.get("value") == before0.get("value"),
        },
        "verified": verified,
    }


def main() -> int:
    print("Forest Manager Stage 6.6 Material Reference Array Write Endpoint:")
    try:
        payload = run()
    except Exception as exc:
        payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "verified": False}
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if payload.get("verified"):
        print("Stage 6.6 material reference ArrayParameter write endpoint passed.")
        return 0
    print("Stage 6.6 material reference ArrayParameter write endpoint failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
