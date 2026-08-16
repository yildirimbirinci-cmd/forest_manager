from __future__ import annotations

import json
from dataclasses import asdict

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.areas import AreaRecordsAdapter


def _normalized_record(record) -> dict[str, object]:
    data = asdict(record)
    data.pop("raw", None)
    data.pop("index", None)
    data.pop("area_id", None)
    return data


def _normalized_patch(patch) -> dict[str, object]:
    return asdict(patch)


def main() -> int:
    print("Forest Manager Stage 5D.42 Area Record No-op Roundtrip Boundary:")
    try:
        service = ForestPackControlService()
        adapter = AreaRecordsAdapter(service)
        forests = service.list_forests()
        forest_reports: list[dict[str, object]] = []
        total_slots = 0
        total_plans = 0

        for forest_name in forests:
            inventory = service.inventory(forest_name)
            arid = next(
                (prop for prop in (inventory.get("properties") or []) if prop.get("name") == "aridlist"),
                None,
            )
            metadata = (arid or {}).get("array_metadata") or {}
            count = int(metadata.get("count") or 0)
            slot_reports: list[dict[str, object]] = []

            for index in range(1, count + 1):
                before = adapter.read_record(forest_name, index)
                patch = adapter.no_op_roundtrip_plan(forest_name, index)
                plan_preserved = _normalized_record(before) == _normalized_patch(patch)
                if not plan_preserved:
                    raise RuntimeError(f"No-op roundtrip plan changed area values: {forest_name}[{index}]")
                total_slots += 1
                total_plans += 1
                slot_reports.append({
                    "index": index,
                    "area_id": before.area_id,
                    "name": before.name,
                    "active": before.active,
                    "node_name": before.node_name,
                    "area_type": before.area_type,
                    "include_exclude": before.include_exclude,
                    "width": before.width,
                    "scale": before.scale,
                    "z_offset": before.z_offset,
                    "plan_preserved": plan_preserved,
                    "write_executed": False,
                    "rollback_executed": False,
                })

            forest_reports.append({"forest_name": forest_name, "area_count": count, "slots": slot_reports})

        result = {
            "ok": True,
            "forest_count": len(forests),
            "slot_count": total_slots,
            "plan_count": total_plans,
            "operation_count": 0,
            "rollback_step_count": 0,
            "forests": forest_reports,
            "policy": {
                "existing_slots_only": True,
                "array_resize": False,
                "no_op_values_only": True,
                "plan_verification": True,
                "writes_executed": False,
                "write_verification": False,
                "rollback_executed": False,
                "final_state_preserved": True,
                "armaplist_write": False,
                "arpaintlist_write": False,
                "runtime_write_boundary": True,
                "write_boundary_reason": "Verified bridge exposes discovery only; array/reference write and rollback endpoints are absent.",
            },
            "verified": True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.42 area record no-op roundtrip capability boundary passed.")
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__ + ": " + str(exc), "verified": False}, indent=2, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
