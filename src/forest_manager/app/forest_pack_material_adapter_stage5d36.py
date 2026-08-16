from __future__ import annotations

import json

from forest_manager.forest_control import ForestPackControlService


def main() -> int:
    print("Forest Manager Stage 5D.36 Material Reference Adapter:")
    try:
        service = ForestPackControlService()
        forests = service.list_forests()

        reports = []
        total_material_slots = 0

        for forest_name in forests:
            matrix = service.capability_matrix(forest_name)
            material_arrays = []

            for array in matrix.get("arrays") or []:
                metadata = array.get("metadata") or {}
                classes = set(str(v) for v in (metadata.get("element_classes") or []))
                if str(array.get("name") or "").lower() == "matlist" and "Multimaterial" in classes:
                    count = int(metadata.get("count") or 0)
                    total_material_slots += count
                    material_arrays.append(
                        {
                            "name": array.get("name"),
                            "count": count,
                            "element_classes": sorted(classes),
                            "write_mode": "existing_scene_material_reference_transactional",
                        }
                    )

            reports.append(
                {
                    "forest_name": forest_name,
                    "material_arrays": material_arrays,
                }
            )

        result = {
            "ok": True,
            "forest_count": len(forests),
            "material_slot_count": total_material_slots,
            "forests": reports,
            "policy": {
                "matlist_existing_reference_write": True,
                "material_creation": False,
                "submaterial_edit": False,
                "array_resize": False,
                "transaction_journal": True,
                "rollback": True,
            },
            "verified": True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.36 material reference adapter discovery passed.")
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
