from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

from PIL import Image
from typing import Any

from forest_manager.forest_control.plant_group_execution import execute_plant_group_manifest
from forest_manager.forest_control.service import ForestPackControlService
from forest_manager.max_bridge.runtime_bridge import (
    ensure_current_bridge,
    get_single_forest_distribution_diagnostics,
    get_single_forest_area_bounds,
    read_plant_group_manifest,
)


def _array_values(service: ForestPackControlService, forest: str, prop: str, count: int) -> list[Any]:
    values: list[Any] = []
    for index in range(count):
        values.append(service.get_array_element(forest, prop, index, preflight=False).get("value"))
    return values


def main() -> int:
    started = time.perf_counter()
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    def check(name: str, condition: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": bool(condition), "detail": detail})

    try:
        bridge = ensure_current_bridge()
        check("bridge_preflight", bool(bridge.get("ok")), bridge.get("data"))

        service = ForestPackControlService()
        forests = list(service.list_forests(preflight=False))
        check("forest_exists", "FM_Forest_001" in forests, forests)
        forest = "FM_Forest_001"

        manifest = read_plant_group_manifest()
        groups = manifest.get("groups") if isinstance(manifest, dict) else None
        check("manifest_three_groups", isinstance(groups, list) and len(groups) == 3, len(groups) if isinstance(groups, list) else None)

        rebuild_started = time.perf_counter()
        rebuild = execute_plant_group_manifest(manifest, service=service, strict_acceptance=False)
        rebuild_seconds = time.perf_counter() - rebuild_started
        check("scene_rebuild", rebuild.get("verified") is True, rebuild)
        map_binding = rebuild.get("map_binding") if isinstance(rebuild, dict) else None
        check(
            "color_id_map_tiling_enabled",
            isinstance(map_binding, dict) and map_binding.get("map_u_tile") is True and map_binding.get("map_v_tile") is True,
            {
                "map_u_tile": map_binding.get("map_u_tile") if isinstance(map_binding, dict) else None,
                "map_v_tile": map_binding.get("map_v_tile") if isinstance(map_binding, dict) else None,
            },
        )

        inventory = service.inventory(forest, preflight=False)
        properties = inventory.get("properties") or []
        def array_count(prop_name: str) -> int:
            item = next((x for x in properties if isinstance(x, dict) and str(x.get("name") or "").lower() == prop_name.lower()), None)
            meta = item.get("array_metadata") if isinstance(item, dict) else None
            return int((meta or {}).get("count") or 0) if isinstance(meta, dict) else 0

        geometry_count = array_count("specidlist")
        area_count = array_count("arnamelist")
        check("geometry_count_3", geometry_count == 3, geometry_count)
        check("area_count_2", area_count == 2, area_count)

        if geometry_count > 0:
            specids = [int(v or 0) for v in _array_values(service, forest, "specidlist", geometry_count)]
            names = [str(v or "") for v in _array_values(service, forest, "namelist", geometry_count)]
            cobj = [str(v or "") for v in _array_values(service, forest, "cobjlist", geometry_count)]
            geom = [int(v or 0) for v in _array_values(service, forest, "geomlist", geometry_count)]
            radius = [int(v or 0) for v in _array_values(service, forest, "radiuslist", geometry_count)]
            scale = [float(v or 0.0) for v in _array_values(service, forest, "ScaleList", geometry_count)]
            check("species_ids_unique", len(set(specids)) == 3 and all(v > 0 for v in specids), specids)
            check("geometry_names_present", all(names), names)
            check("custom_objects_present", all(cobj), cobj)
            check("geometry_runtime_enabled", all(v != 0 for v in geom), geom)
            check("collision_radius_positive", all(v > 0 for v in radius), radius)
            check("scale_values_positive", all(v > 0.0 for v in scale), scale)

        if area_count > 0:
            area_names = [str(v or "") for v in _array_values(service, forest, "arnamelist", area_count)]
            active = [bool(v) for v in _array_values(service, forest, "pf_aractivelist", area_count)]
            spec_select = [str(v or "") for v in _array_values(service, forest, "arspeclist", area_count)]
            check("no_managed_group_areas", not any(name.upper().startswith("FM_GROUP_") for name in area_names), area_names)
            check("one_real_active_area", sum(1 for value in active if value) == 1, active)
            check("active_area_selects_three_species", any(all(token in value.split() for token in ("1", "2", "3")) for value in spec_select), spec_select)

        bounds = get_single_forest_area_bounds(forest)
        diagnostics = get_single_forest_distribution_diagnostics(forest)
        check("image_distribution_mode", int(diagnostics.get("distmode", -1)) == 0, diagnostics.get("distmode"))
        projection_ok = (
            abs(float(diagnostics.get("units_x") or 0.0) - float(bounds.get("width_system") or 0.0)) <= 0.01
            and abs(float(diagnostics.get("units_y") or 0.0) - float(bounds.get("height_system") or 0.0)) <= 0.01
        )
        check("map_projection_fits_active_area", projection_ok, {"bounds": bounds, "units_x": diagnostics.get("units_x"), "units_y": diagnostics.get("units_y")})
        check("color_id_map_density_enabled", diagnostics.get("densityMap") is True, diagnostics.get("densityMap"))
        check("color_id_diversity", int(diagnostics.get("diversity_value", -1)) == 1, diagnostics.get("diversity_value"))
        check("map_bound", bool(str(diagnostics.get("map_path") or "").strip()), diagnostics.get("map_path"))

        map_path = Path(str(diagnostics.get("map_path") or ""))
        map_size = None
        if map_path.is_file():
            with Image.open(map_path).convert("RGB") as image:
                counts = Counter(image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata())
                palette = ((255, 0, 0), (0, 255, 0), (0, 0, 255))
                palette_counts = {str(color): int(counts.get(color, 0)) for color in palette}
                map_size = image.size
                check("map_contains_three_species_colors", all(value > 0 for value in palette_counts.values()), {"size": image.size, "counts": palette_counts})
        else:
            check("map_contains_three_species_colors", False, str(map_path))

        # Zero generated items is never a valid successful acceptance when the
        # Area is active and the RGB map contains planting pixels. Previously
        # this was incorrectly skipped as a small-area warning.
        generated_items = int(diagnostics.get("generated_items") or 0)
        missing = [int(v) for v in (diagnostics.get("missing_species_ids") or [])]
        check("generated_items_nonzero", generated_items > 0, {"generated_items": generated_items})
        if generated_items >= 12:
            check("generated_species_coverage", not missing, {"generated_items": generated_items, "missing_species_ids": missing})
        elif generated_items > 0:
            warnings.append(
                f"Generated item count is only {generated_items}; all three species may not be statistically represented on this small Area."
            )
            check("generated_species_coverage", True, {"generated_items": generated_items, "missing_species_ids": missing, "skipped": True})
        else:
            check("generated_species_coverage", False, {"generated_items": 0, "missing_species_ids": missing})

        units = service.scene_units(preflight=False)
        if map_size and units.one_meter_system_units > 0.0:
            source_mask = Path(__file__).resolve().parents[3] / "resources" / "generated_masks" / "stage5d18" / "FM_Mask_01_foreground_mass.png"
            if source_mask.is_file():
                with Image.open(source_mask) as source_image:
                    authored_pitch = (75.0 * units.one_meter_system_units) / max(1, source_image.size[0])
                actual_pitch_x = float(diagnostics.get("units_x") or 0.0) / max(1, map_size[0])
                actual_pitch_y = float(diagnostics.get("units_y") or 0.0) / max(1, map_size[1])
                tolerance = max(0.5, authored_pitch * 0.20)
                check(
                    "map_pixel_pitch_preserved",
                    abs(actual_pitch_x - authored_pitch) <= tolerance and abs(actual_pitch_y - authored_pitch) <= tolerance,
                    {
                        "authored_pitch_system": authored_pitch,
                        "actual_pitch_x_system": actual_pitch_x,
                        "actual_pitch_y_system": actual_pitch_y,
                        "map_size": map_size,
                    },
                )

        check("scene_unit_conversion", units.one_meter_system_units > 0.0, {
            "display_unit": units.display_unit,
            "system_type": units.system_type,
            "one_meter_system_units": units.one_meter_system_units,
        })

        failed = [item for item in checks if not item["passed"]]
        result = {
            "ok": not failed,
            "forest": forest,
            "bridge": bridge.get("data"),
            "rebuild_seconds": round(rebuild_seconds, 3),
            "total_seconds": round(time.perf_counter() - started, 3),
            "checks": checks,
            "warnings": warnings,
            "diagnostics": diagnostics,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if not failed else 1
    except Exception as exc:
        result = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "checks": checks,
            "warnings": warnings,
            "total_seconds": round(time.perf_counter() - started, 3),
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
