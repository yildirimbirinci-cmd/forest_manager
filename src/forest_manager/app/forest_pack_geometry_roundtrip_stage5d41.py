from __future__ import annotations

import json
from dataclasses import asdict

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.geometry import GeometrySourcesAdapter


def _normalized_record(record) -> dict[str, object]:
    data = asdict(record)
    data.pop("raw", None)
    data.pop("index", None)
    return data


def _normalized_patch(patch) -> dict[str, object]:
    return asdict(patch)


def main() -> int:
    print("Forest Manager Stage 5D.41 Geometry Source No-op Roundtrip Boundary:")
    try:
        service = ForestPackControlService()
        adapter = GeometrySourcesAdapter(service)
        forests = service.list_forests()

        forest_reports: list[dict[str, object]] = []
        total_slots = 0
        total_plans = 0

        for forest_name in forests:
            inventory = service.inventory(forest_name)
            cobj = next(
                (
                    prop
                    for prop in (inventory.get("properties") or [])
                    if prop.get("name") == "cobjlist"
                ),
                None,
            )
            metadata = (cobj or {}).get("array_metadata") or {}
            count = int(metadata.get("count") or 0)
            slot_reports: list[dict[str, object]] = []

            for index in range(1, count + 1):
                before = adapter.read_record(forest_name, index)
                patch = adapter.no_op_roundtrip_plan(forest_name, index)
                record_values = _normalized_record(before)
                planned_values = _normalized_patch(patch)
                plan_preserved = record_values == planned_values
                if not plan_preserved:
                    raise RuntimeError(
                        f"No-op roundtrip plan changed geometry source values: {forest_name}[{index}]"
                    )

                total_slots += 1
                total_plans += 1
                slot_reports.append(
                    {
                        "index": index,
                        "source_node": before.source_node,
                        "material_name": before.material_name,
                        "name": before.name,
                        "probability": before.probability,
                        "scale": before.scale,
                        "plan_preserved": plan_preserved,
                        "write_executed": False,
                        "rollback_executed": False,
                    }
                )

            forest_reports.append(
                {"forest_name": forest_name, "source_count": count, "slots": slot_reports}
            )

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
                "coloridlist_write": False,
                "runtime_write_boundary": True,
                "write_boundary_reason": "Verified bridge exposes discovery only; array/reference write and rollback endpoints are absent.",
            },
            "verified": True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.41 geometry source no-op roundtrip capability boundary passed.")
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {"ok": False, "error": type(exc).__name__ + ": " + str(exc), "verified": False},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
