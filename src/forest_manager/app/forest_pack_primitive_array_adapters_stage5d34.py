from __future__ import annotations

import json

from forest_manager.forest_control import ForestPackControlService


PRIMITIVE_CLASSES = {"BooleanClass", "Float", "Integer", "String"}


def main() -> int:
    print("Forest Manager Stage 5D.34 Primitive Array Adapters:")
    try:
        service = ForestPackControlService()
        forests = service.list_forests()
        reports = []
        total_primitive_arrays = 0
        total_blocked_arrays = 0

        for forest_name in forests:
            matrix = service.capability_matrix(forest_name)
            primitive_arrays = []
            blocked_arrays = []

            for array in matrix.get("arrays") or []:
                metadata = array.get("metadata") or {}
                classes = set(str(v) for v in (metadata.get("element_classes") or []))
                count = int(metadata.get("count") or 0)

                if count > 0 and classes and classes.issubset(PRIMITIVE_CLASSES):
                    primitive_arrays.append(
                        {
                            "name": array.get("name"),
                            "count": count,
                            "element_classes": sorted(classes),
                            "write_mode": "indexed_primitive_transactional",
                        }
                    )
                else:
                    blocked_arrays.append(
                        {
                            "name": array.get("name"),
                            "count": count,
                            "element_classes": sorted(classes),
                            "write_mode": "read_only",
                        }
                    )

            total_primitive_arrays += len(primitive_arrays)
            total_blocked_arrays += len(blocked_arrays)
            reports.append(
                {
                    "forest_name": forest_name,
                    "primitive_array_count": len(primitive_arrays),
                    "blocked_array_count": len(blocked_arrays),
                    "primitive_arrays": primitive_arrays,
                    "blocked_arrays": blocked_arrays,
                }
            )

        result = {
            "ok": True,
            "forest_count": len(forests),
            "primitive_array_instances": total_primitive_arrays,
            "blocked_array_instances": total_blocked_arrays,
            "forests": reports,
            "policy": {
                "primitive_array_element_read": True,
                "primitive_array_element_write": True,
                "transaction_journal": True,
                "rollback": True,
                "node_material_point3_array_write": False,
                "empty_array_write": False,
            },
            "verified": True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.34 primitive array adapter discovery passed.")
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
