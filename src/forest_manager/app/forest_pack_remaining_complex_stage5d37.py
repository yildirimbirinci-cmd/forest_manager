from __future__ import annotations

import json

from forest_manager.forest_control import ForestPackControlService


def main() -> int:
    print("Forest Manager Stage 5D.37 Time, Bitmap and Curve Discovery:")
    try:
        service = ForestPackControlService()
        forests = service.list_forests()

        reports = []
        totals = {"Time": 0, "Bitmaptexture": 0, "CurveControl": 0}

        for forest_name in forests:
            inventory = service.inventory(forest_name)
            properties = inventory.get("properties") or []

            time_props = []
            bitmap_props = []
            curve_props = []

            for prop in properties:
                value_class = str(prop.get("value_class") or "")
                name = str(prop.get("name") or "")
                if value_class == "Time":
                    time_props.append(name)
                    totals["Time"] += 1
                elif value_class == "Bitmaptexture":
                    bitmap_props.append(name)
                    totals["Bitmaptexture"] += 1
                elif value_class == "CurveControl":
                    metadata = service.curve_metadata(forest_name, name)
                    curve_props.append(metadata)
                    totals["CurveControl"] += 1

            reports.append(
                {
                    "forest_name": forest_name,
                    "time_properties": time_props,
                    "bitmap_properties": bitmap_props,
                    "curve_properties": curve_props,
                }
            )

        result = {
            "ok": True,
            "forest_count": len(forests),
            "property_type_totals": totals,
            "forests": reports,
            "policy": {
                "time_read_write": True,
                "bitmap_existing_reference_write": True,
                "curve_control_read": True,
                "curve_control_write": False,
                "transaction_journal": True,
                "rollback": True,
            },
            "verified": True,
        }

        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.37 remaining complex property discovery passed.")
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
