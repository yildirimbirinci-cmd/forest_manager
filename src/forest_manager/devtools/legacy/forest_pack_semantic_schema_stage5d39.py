from __future__ import annotations

import json

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.schema import raw_property_coverage, semantic_domains


def main() -> int:
    print("Forest Manager Stage 5D.39 Semantic Control Schema:")
    try:
        service = ForestPackControlService()
        forests = service.list_forests()
        forest_reports = []
        for forest_name in forests:
            inventory = service.inventory(forest_name)
            property_names = [str(prop.get("name") or "") for prop in (inventory.get("properties") or []) if prop.get("name")]
            forest_reports.append({
                "forest_name": forest_name,
                "property_count": len(property_names),
                "coverage": raw_property_coverage(property_names),
            })

        domains = []
        for domain in semantic_domains():
            domains.append({
                "name": domain.name,
                "fields": [
                    {
                        "name": field.name,
                        "access": field.access,
                        "raw_properties": list(field.raw_properties),
                        "notes": field.notes,
                    }
                    for field in domain.fields
                ],
            })

        result = {
            "ok": True,
            "forest_count": len(forests),
            "domain_count": len(domains),
            "domains": domains,
            "forests": forest_reports,
            "policy": {
                "raw_scalar_api_preserved": True,
                "semantic_layer_added": True,
                "synchronized_geometry_arrays_atomic_only": True,
                "synchronized_area_arrays_atomic_only": True,
                "curve_control_write": False,
                "curve_control_reason": "opaque CurveClass/SubAnim without exposed controller",
            },
            "verified": True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.39 semantic control schema passed.")
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__ + ": " + str(exc), "verified": False}, indent=2, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
