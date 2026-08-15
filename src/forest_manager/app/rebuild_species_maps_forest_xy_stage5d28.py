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

    print("Forest Manager Stage 5D.28 Forest XY Tiled Species Map Rebuild:")
    try:
        ensure_current_bridge()

        # Return to the protected state before replacing distribution maps.
        _require_ok(send_command("ROLLBACK_SPECIES_LAYER_PREVIEW"), "ROLLBACK_SPECIES_LAYER_PREVIEW")

        output_dir = Path(args.output_dir).resolve()
        report = generate_species_masks(output_dir)
        if not report.get("verified"):
            raise RuntimeError("Full-tile species mask generation did not verify.")
        if report.get("policy") != "deterministic_species_masks_v1":
            raise RuntimeError("Unexpected species mask policy: " + str(report.get("policy")))

        layers = report.get("layers") or []
        if len(layers) != 3:
            raise RuntimeError("Exactly three generated species masks are required.")
        paths = [str(Path(layer["soft_mask"]).resolve()) for layer in layers]

        bind_command = "BIND_SPECIES_DISTRIBUTION_MASKS|" + "|".join(paths)
        binding = _require_ok(send_command(bind_command), "BIND_SPECIES_DISTRIBUTION_MASKS")
        projection = _require_ok(
            send_command("CONFIGURE_SPECIES_MAP_PROJECTION"),
            "CONFIGURE_SPECIES_MAP_PROJECTION",
        )
        composition = _require_ok(
            send_command("ACTIVATE_ALL_SPECIES_LAYERS"),
            "ACTIVATE_ALL_SPECIES_LAYERS",
        )

        if projection.get("projection") != "forest_xy_tiled_75m":
            raise RuntimeError("Forest XY tiled projection did not verify.")
        projected_layers = projection.get("layers") or []
        if len(projected_layers) != 3:
            raise RuntimeError("Projection did not return three species layers.")
        for layer in projected_layers:
            if layer.get("u_tile") is not True or layer.get("v_tile") is not True:
                raise RuntimeError("Distribution bitmap tiling is not enabled on all species layers.")
            if abs(float(layer.get("density_meters_x", 0.0)) - 75.0) > 0.001:
                raise RuntimeError("Density Units X changed from 75.0 m.")
            if abs(float(layer.get("density_meters_y", 0.0)) - 75.0) > 0.001:
                raise RuntimeError("Density Units Y changed from 75.0 m.")

        active_layers = composition.get("layers") or []
        if len(active_layers) != 3:
            raise RuntimeError("Three active species layers were not returned.")
        if any(int(layer.get("generated_items") or 0) <= 0 for layer in active_layers):
            raise RuntimeError("At least one species layer generated zero Forest items.")

        result = {
            "ok": True,
            "masks": report,
            "binding_verified": bool(binding.get("verified")),
            "projection": projection,
            "composition": composition,
            "verified": True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.28 Forest XY tiled three-species composition passed.")
        return 0
    except Exception as exc:
        print("Stage 5D.28 error:", type(exc).__name__ + ": " + str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
