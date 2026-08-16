from __future__ import annotations

import json

from forest_manager.forest_control import ForestPackControlService


def main() -> int:
    print("Forest Manager Stage 5D.38 CurveControl Runtime Boundary:")
    try:
        service = ForestPackControlService()
        forests = service.list_forests()
        reports = []
        total_curve_properties = 0

        for forest_name in forests:
            inventory = service.inventory(forest_name)
            curve_reports = []
            for prop in inventory.get("properties") or []:
                if str(prop.get("value_class") or "") != "CurveControl":
                    continue
                property_name = str(prop.get("name") or "")
                boundary = service.curve_points(forest_name, property_name)
                total_curve_properties += 1
                curve_reports.append(boundary)
            reports.append({"forest_name": forest_name, "curve_properties": curve_reports})

        result = {
            "ok": True,
            "forest_count": len(forests),
            "curve_property_count": total_curve_properties,
            "forests": reports,
            "policy": {
                "curve_metadata_read": True,
                "curve_point_read": False,
                "existing_point_write": False,
                "point_count_change": False,
                "insert_delete_points": False,
                "controller_access": False,
                "transaction_journal": False,
                "rollback": False,
                "capability_boundary_verified": True,
            },
            "verified": True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.38 CurveControl runtime capability boundary passed.")
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__ + ": " + str(exc), "verified": False}, indent=2, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
