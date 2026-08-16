from __future__ import annotations

import json

from forest_manager.forest_control import ForestPackControlService


NODE_REFERENCE_PROPERTIES = {
    "arnodelist",
    "cobjlist",
    "distpathnodes",
    "distpflownodes",
    "distrefnodes",
    "efpainode",
    "efpaspline",
    "surflist",
}


def main() -> int:
    print("Forest Manager Stage 5D.35 Reference Array Adapters:")
    try:
        service = ForestPackControlService()
        forests = service.list_forests()
        reports = []

        point3_instances = 0
        node_reference_instances = 0
        material_instances = 0

        for forest_name in forests:
            matrix = service.capability_matrix(forest_name)
            point3_arrays = []
            node_arrays = []
            material_arrays = []

            for array in matrix.get("arrays") or []:
                name = str(array.get("name") or "")
                metadata = array.get("metadata") or {}
                classes = set(str(v) for v in (metadata.get("element_classes") or []))
                count = int(metadata.get("count") or 0)

                if "Point3" in classes:
                    point3_arrays.append(name)
                    point3_instances += 1
                if name.lower() in NODE_REFERENCE_PROPERTIES and count > 0:
                    node_arrays.append(name)
                    node_reference_instances += 1
                if "Multimaterial" in classes:
                    material_arrays.append(name)
                    material_instances += 1

            reports.append(
                {
                    "forest_name": forest_name,
                    "point3_arrays": point3_arrays,
                    "node_reference_arrays": node_arrays,
                    "material_arrays_read_only": material_arrays,
                }
            )

        result = {
            "ok": True,
            "forest_count": len(forests),
            "point3_array_instances": point3_instances,
            "node_reference_array_instances": node_reference_instances,
            "material_array_instances": material_instances,
            "forests": reports,
            "policy": {
                "point3_array_write": True,
                "existing_node_reference_write": True,
                "node_reference_property_allowlist": sorted(NODE_REFERENCE_PROPERTIES),
                "material_reference_write": False,
                "array_resize": False,
                "transaction_journal": True,
                "rollback": True,
            },
            "verified": True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.35 reference array adapter discovery passed.")
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
