from __future__ import annotations

import json

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.schema import raw_property_coverage, semantic_domains


def main() -> int:
    print("Forest Manager Stage 5D.52 Semantic Schema Promotion:")
    try:
        service = ForestPackControlService()
        forests = service.list_forests()
        reports = []

        for forest_name in forests:
            inventory = service.inventory(forest_name)
            rows = (
                inventory.get("properties")
                or inventory.get("inventory")
                or inventory.get("items")
                or []
            )
            if isinstance(rows, dict):
                rows = rows.values()

            names = [
                str(row.get("name") or row.get("property_name"))
                for row in rows
                if isinstance(row, dict) and (row.get("name") or row.get("property_name"))
            ]
            coverage = raw_property_coverage(names)
            reports.append(
                {
                    "forest_name": forest_name,
                    "property_count": len(names),
                    "declared_count": coverage["declared_count"],
                    "covered_count": coverage["covered_count"],
                    "undeclared_count": len(coverage["undeclared"]),
                    "undeclared": coverage["undeclared"],
                    "declared_but_missing": coverage["declared_but_missing"],
                }
            )

        result = {
            "ok": True,
            "forest_count": len(forests),
            "domain_count": len(semantic_domains()),
            "forests": reports,
            "policy": {
                "promoted_candidate_count": 40,
                "runtime_writable_promoted": 36,
                "runtime_read_only_promoted": 4,
                "reserved_not_exposed": True,
                "internal_runtime_not_exposed": True,
                "legacy_plugin_not_exposed": True,
                "scene_write": False,
            },
            "verified": all(
                item["property_count"] == 341
                and item["declared_count"] == 281
                and item["covered_count"] == 281
                and item["undeclared_count"] == 60
                and item["declared_but_missing"] == []
                for item in reports
            ),
        }
        if not result["verified"]:
            raise RuntimeError("Stage 5D.52 semantic coverage contract mismatch.")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.52 semantic schema promotion passed.")
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": type(exc).__name__ + ": " + str(exc),
                    "verified": False,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
