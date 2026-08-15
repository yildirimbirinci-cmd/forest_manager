from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command
from forest_manager.placement.species_mask_generator import generate_species_masks


def _require_ok(response: dict, command: str) -> dict:
    if not response.get("ok"):
        raise RuntimeError(f"{command} failed: {response.get('error') or response}")
    return response.get("data") or {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="resources/generated_masks/stage5d18",
        help="Project-relative mask output directory.",
    )
    args = parser.parse_args()

    print("Forest Manager Stage 5D.27 Spline-Clipped Species Mask Rebuild:")

    try:
        ensure_current_bridge()
        area = _require_ok(send_command("GET_FOREST_AREA_POLYGON"), "GET_FOREST_AREA_POLYGON")
        rings_raw = area.get("normalized_rings") or []
        rings = [
            [(float(point[0]), float(point[1])) for point in ring]
            for ring in rings_raw
            if len(ring) >= 3
        ]
        if not rings:
            raise RuntimeError("Forest area polygon did not contain a usable closed ring.")

        # Return to the protected baseline state before replacing Bitmaptexture maps.
        _require_ok(send_command("ROLLBACK_SPECIES_LAYER_PREVIEW"), "ROLLBACK_SPECIES_LAYER_PREVIEW")

        output_dir = Path(args.output_dir).resolve()
        report = generate_species_masks(output_dir, normalized_rings=rings)
        if not report.get("verified") or not report.get("spline_polygon_applied"):
            raise RuntimeError("Spline-clipped species mask generation did not verify.")

        layers = report.get("layers") or []
        if len(layers) != 3:
            raise RuntimeError("Exactly three generated species masks are required.")
        paths = [str(Path(layer["soft_mask"]).resolve()) for layer in layers]

        bind_command = "BIND_SPECIES_DISTRIBUTION_MASKS|" + "|".join(paths)
        binding = _require_ok(send_command(bind_command), "BIND_SPECIES_DISTRIBUTION_MASKS")
        composition = _require_ok(send_command("ACTIVATE_ALL_SPECIES_LAYERS"), "ACTIVATE_ALL_SPECIES_LAYERS")

        active_layers = composition.get("layers") or []
        if len(active_layers) != 3:
            raise RuntimeError("Three active species layers were not returned.")
        if any(int(layer.get("generated_items") or 0) <= 0 for layer in active_layers):
            raise RuntimeError("At least one species layer generated zero Forest items.")

        result = {
            "ok": True,
            "spline": {
                "name": area.get("spline_name"),
                "spline_count": area.get("spline_count"),
                "samples_per_spline": area.get("samples_per_spline"),
                "bounds_width_meters": area.get("bounds_width_meters"),
                "bounds_height_meters": area.get("bounds_height_meters"),
                "coordinate_space": area.get("coordinate_space"),
            },
            "masks": {
                "policy": report.get("policy"),
                "area_pixel_count": report.get("area_pixel_count"),
                "outside_area_pixel_count": report.get("outside_area_pixel_count"),
                "coverage_total_percent": report.get("coverage_total_percent"),
                "exclusive_primary_ownership": report.get("exclusive_primary_ownership"),
                "layers": layers,
            },
            "binding_verified": bool(binding.get("verified")),
            "composition": composition,
            "verified": True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.27 spline-clipped three-species composition passed.")
        return 0
    except Exception as exc:
        print("Stage 5D.27 error:", type(exc).__name__ + ": " + str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
