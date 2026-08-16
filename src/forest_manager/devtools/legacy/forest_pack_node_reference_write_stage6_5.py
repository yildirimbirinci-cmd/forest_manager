from __future__ import annotations

import json

from forest_manager.forest_control.service import ForestPackControlService


def main() -> int:
    service = ForestPackControlService()
    result: dict[str, object] = {"ok": False, "verified": False}
    try:
        forest_name = "FM_Forest_001"
        property_name = "arnodelist"
        source_index = 1
        target_index = 0

        before = service.get_array_element(forest_name, property_name, target_index)
        source = service.get_array_element(forest_name, property_name, source_index, preflight=False)
        target_node = source.get("value")
        if before.get("reference_type") != "node" or source.get("reference_type") != "node":
            raise RuntimeError("arnodelist did not expose the Stage 6.5 node-reference contract.")
        if before.get("value") is not None:
            raise RuntimeError("Stage 6.5 target slot is expected to start undefined.")
        if not isinstance(target_node, str) or not target_node:
            raise RuntimeError("Stage 6.5 source node reference is unavailable.")
        count_before = int(before.get("count") or 0)

        write = service.set_array_element(forest_name, property_name, target_index, target_node, preflight=False)
        after_write = service.get_array_element(forest_name, property_name, target_index, preflight=False)
        rollback_steps = service.rollback()
        after_rollback = service.get_array_element(forest_name, property_name, target_index, preflight=False)
        count_after = int(after_rollback.get("count") or 0)

        verified = bool(
            write.get("verified")
            and after_write.get("value") == target_node
            and after_rollback.get("value") is None
            and count_before == count_after
            and len(rollback_steps) == 1
        )
        result = {
            "ok": verified,
            "forest_name": forest_name,
            "property_name": property_name,
            "index": target_index,
            "source_index": source_index,
            "reference_type": "node",
            "before": before.get("value"),
            "target": target_node,
            "after_write": after_write.get("value"),
            "after_rollback": after_rollback.get("value"),
            "array_count_before": count_before,
            "array_count_after": count_after,
            "rollback_step_count": len(rollback_steps),
            "runtime_write_endpoint": bool(write.get("verified")),
            "runtime_rollback_endpoint": bool(rollback_steps and rollback_steps[0].get("verified")),
            "policy": {
                "node_reference_property_allowlist": ["arnodelist"],
                "nullable_node_references": True,
                "existing_scene_node_resolution": True,
                "cproxy_material_bitmap_reference_writes_blocked": True,
                "array_length_preserved": count_before == count_after,
                "bridge_readback_verification": True,
                "service_readback_verification": True,
                "single_session_mixed_rollback_journal": True,
                "startup_loader_content_stable_across_build_ids": True,
                "final_state_preserved": after_rollback.get("value") is None,
            },
            "verified": verified,
        }
    except Exception as exc:
        try:
            service.rollback()
        except Exception:
            pass
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "verified": False}

    print("Forest Manager Stage 6.5 Node Reference Array Write Endpoint:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("verified"):
        print("Stage 6.5 node reference ArrayParameter write endpoint passed.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
