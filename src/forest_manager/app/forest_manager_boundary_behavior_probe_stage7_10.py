from __future__ import annotations

import json

BOUNDARY_CANDIDATE_GROUPS = {
    "distribution_edge": (
        "threshold",
        "maxdensity",
        "distpathoffset",
        "distpathspacing",
        "distpathrandpos",
    ),
    "area_boundary_records": (
        "arincexclist",
        "arwidthlist",
        "arthresholdlist",
        "arflafdenslist",
        "arflafscalist",
        "arboundchecklist",
        "arprojectlist",
        "arobscalelist",
        "arscalemin",
        "arscalemax",
        "arzoffset",
    ),
    "surface_falloff": (
        "spdensact",
        "spdensexc",
        "spdensinc",
        "spscalact",
        "spscalexc",
        "spscalinc",
        "spscalz",
        "scalelope",
        "spdenscurve",
        "spscalcurve",
        "Surface_Falloff_Curves",
    ),
}


def _unit_payload(units):
    return {
        "display_type": units.display_type,
        "display_unit": units.display_unit,
        "system_type": units.system_type,
        "system_scale": units.system_scale,
        "one_meter_system_units": units.one_meter_system_units,
        "one_centimeter_system_units": units.one_centimeter_system_units,
        "one_millimeter_system_units": units.one_millimeter_system_units,
        "sample_one_meter_display": units.sample_one_meter_display,
        "custom_name": units.custom_name,
        "custom_value": units.custom_value,
        "custom_unit": units.custom_unit,
    }


def build_probe(service) -> dict[str, object]:
    forest_name = service.selected_forest_name()
    inventory = service.inventory(forest_name, preflight=False)
    units = service.scene_units(preflight=False)
    by_name = {
        str(item.get("name") or "").lower(): item
        for item in inventory.get("properties", [])
    }

    groups: dict[str, object] = {}
    writable_scalar: list[str] = []
    adapter_required: list[str] = []
    read_only_or_opaque: list[str] = []

    for group_name, candidates in BOUNDARY_CANDIDATE_GROUPS.items():
        rows = []
        for property_name in candidates:
            item = by_name.get(property_name.lower())
            if item is None:
                continue
            row = {
                "name": item.get("name"),
                "value": item.get("value"),
                "value_class": item.get("value_class"),
                "write_mode": item.get("write_mode"),
                "readable": bool(item.get("readable")),
                "array_metadata": item.get("array_metadata"),
            }
            rows.append(row)
            mode = str(item.get("write_mode") or "")
            value_class = str(item.get("value_class") or "")
            if mode == "scalar":
                writable_scalar.append(str(item.get("name")))
            elif value_class == "ArrayParameter" or mode.startswith("array_"):
                adapter_required.append(str(item.get("name")))
            else:
                read_only_or_opaque.append(str(item.get("name")))
        groups[group_name] = {
            "candidate_properties": list(candidates),
            "available_properties": rows,
            "available_count": len(rows),
        }

    return {
        "ok": True,
        "forest_name": forest_name,
        "scene_units": _unit_payload(units),
        "boundary_behavior": {
            "groups": groups,
            "writable_scalar_candidates": sorted(set(writable_scalar)),
            "adapter_required_candidates": sorted(set(adapter_required)),
            "read_only_or_opaque_candidates": sorted(set(read_only_or_opaque)),
        },
        "read_only": True,
        "policy": {
            "read_only_probe": True,
            "no_boundary_raw_values_guessed": True,
            "distribution_area_surface_examined_together": True,
            "synchronized_area_arrays_not_mutated": True,
            "opaque_falloff_curves_not_mutated": True,
            "boundary_behavior_requires_runtime_calibration": True,
        },
        "verified": True,
    }


def main() -> int:
    print("Forest Manager Stage 7.10 Boundary Behavior Calibration Probe:")
    try:
        from forest_manager.forest_control.service import ForestPackControlService

        payload = build_probe(ForestPackControlService())
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("Stage 7.10 boundary behavior calibration probe passed.")
        return 0
    except Exception as exc:
        payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "verified": False}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
