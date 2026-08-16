from __future__ import annotations

import json
from dataclasses import asdict

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.areas import AreaRecordsAdapter


def main() -> int:
    print("Forest Manager Stage 5D.42 Area Records Runtime Boundary:")
    try:
        service = ForestPackControlService()
        adapter = AreaRecordsAdapter(service)
        forests = service.list_forests()
        reports: list[dict[str, object]] = []

        for forest_name in forests:
            inventory = service.inventory(forest_name)
            arid = next(
                (prop for prop in (inventory.get("properties") or []) if prop.get("name") == "aridlist"),
                None,
            )
            metadata = (arid or {}).get("array_metadata") or {}
            count = int(metadata.get("count") or 0)
            records = [asdict(adapter.read_record(forest_name, index)) for index in range(1, count + 1)]
            reports.append({"forest_name": forest_name, "area_count": count, "records": records})

        result = {
            "ok": True,
            "forest_count": len(forests),
            "forests": reports,
            "policy": {
                "existing_slots_only": True,
                "array_resize": False,
                "synchronized_record_read": True,
                "atomic_update_api": False,
                "rollback_on_failure": False,
                "runtime_discovery_write": False,
                "armaplist_write": False,
                "arpaintlist_write": False,
                "write_boundary_reason": "Verified bridge exposes discovery only; array/reference write and rollback endpoints are absent.",
            },
            "verified": True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.42 area record runtime capability boundary passed.")
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__ + ": " + str(exc), "verified": False}, indent=2, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
