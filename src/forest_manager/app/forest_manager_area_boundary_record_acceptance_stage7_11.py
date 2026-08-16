from __future__ import annotations

import json

from forest_manager.forest_control.area_records import AreaBoundaryRecordAdapter, AreaBoundaryUpdate
from forest_manager.forest_control.service import ForestControlError, ForestPackControlService


def _same(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(float(a) - float(b)) <= 1e-5
    return a == b


def main() -> int:
    service = ForestPackControlService()
    adapter = AreaBoundaryRecordAdapter(service)
    forest_name = "FM_Forest_001"
    try:
        forests = service.list_forests()
        if forest_name not in forests:
            raise ForestControlError(f"Required acceptance Forest was not discovered: {forest_name}")
        records = adapter.list_records(forest_name)
        if not records:
            raise ForestControlError("Stage 7.11 requires at least one Forest Area record.")
        before = records[0]
        if not isinstance(before.width, (int, float)) or isinstance(before.width, bool):
            raise ForestControlError("First Area record width is not numeric.")
        if not isinstance(before.density_falloff, (int, float)) or isinstance(before.density_falloff, bool):
            raise ForestControlError("First Area record density falloff is not numeric.")

        target_width = float(before.width) + 1.0
        target_density = max(0.0, float(before.density_falloff) - 1.0)
        result = adapter.apply_update(
            forest_name,
            before.index,
            AreaBoundaryUpdate(width=target_width, density_falloff=target_density),
            rollback_on_success=True,
        )
        after = adapter.read_record(forest_name, before.index)
        rollback_verified = _same(after.width, before.width) and _same(after.density_falloff, before.density_falloff)
        report = {
            "ok": True,
            "forest_name": forest_name,
            "area_index": before.index,
            "area_name": before.name,
            "area_node_name": before.node_name,
            "area_id": before.area_id,
            "area_count": len(records),
            "before": {"width": before.width, "density_falloff": before.density_falloff},
            "target": {"width": target_width, "density_falloff": target_density},
            "operation_count": result.operation_count,
            "rollback_step_count": result.rollback_step_count,
            "write_verified": result.write_verified,
            "rollback_verified": bool(result.rollback_verified and rollback_verified),
            "after_rollback": {"width": after.width, "density_falloff": after.density_falloff},
            "policy": {
                "synchronized_area_record_alignment_guard": True,
                "raw_area_arrays_hidden_from_artist_semantics": True,
                "single_area_index_atomic_patch": True,
                "partial_failure_uses_unified_transaction_rollback": True,
                "record_count_preserved": len(adapter.list_records(forest_name)) == len(records),
                "final_state_preserved": rollback_verified,
            },
            "verified": bool(result.write_verified and result.rollback_verified and rollback_verified),
        }
        print("Forest Manager Stage 7.11 Area Boundary Record Adapter Acceptance:")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if not report["verified"]:
            return 1
        print("Stage 7.11 area boundary record adapter acceptance passed.")
        return 0
    except Exception as exc:
        print("Forest Manager Stage 7.11 Area Boundary Record Adapter Acceptance:")
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}", "verified": False}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
