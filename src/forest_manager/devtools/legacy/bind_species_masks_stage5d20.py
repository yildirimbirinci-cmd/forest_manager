from __future__ import annotations

import json
import sys
from pathlib import Path

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


MASK_NAMES = (
    "FM_Mask_01_foreground_mass.png",
    "FM_Mask_02_mid_accent.png",
    "FM_Mask_03_structural_shrub.png",
)


def main() -> int:
    mask_dir = Path("resources/generated_masks/stage5d18").resolve()
    mask_paths = [mask_dir / name for name in MASK_NAMES]

    missing = [str(path) for path in mask_paths if not path.is_file()]
    if missing:
        print("Stage 5D.20 error: required mask files are missing:")
        for path in missing:
            print(path)
        return 2

    if any("|" in str(path) for path in mask_paths):
        print("Stage 5D.20 error: mask path contains unsupported '|' character.")
        return 3

    try:
        ensure_current_bridge()
        command = "BIND_SPECIES_DISTRIBUTION_MASKS|" + "|".join(str(path) for path in mask_paths)
        response = send_command(command)
    except Exception as exc:
        print("Stage 5D.20 error:", type(exc).__name__ + ": " + str(exc))
        return 4

    print("Forest Manager Stage 5D.20 Bind Species Distribution Masks:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        return 5

    data = response.get("data") or {}
    layers = data.get("layers") or []

    if not data.get("verified") or not data.get("transactional"):
        return 6
    if not data.get("prepared_layers_disabled"):
        return 7
    if not data.get("density_units_preserved"):
        return 8
    if not data.get("legacy_forest_active"):
        return 9
    if len(layers) != 3:
        return 10

    for expected_path, layer in zip(mask_paths, layers):
        if not layer.get("verified"):
            return 11
        if not layer.get("disabled"):
            return 12
        if not layer.get("densityMap"):
            return 13
        if int(layer.get("distmode", -1)) != 0:
            return 14
        if abs(float(layer.get("density_meters_x", 0.0)) - 75.0) > 0.001:
            return 15
        if abs(float(layer.get("density_meters_y", 0.0)) - 75.0) > 0.001:
            return 16
        if Path(layer.get("mask_path", "")).resolve() != expected_path:
            return 17

    print("Stage 5D.20 species distribution mask binding passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
