from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from forest_manager.placement.species_mask_generator import generate_species_masks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="resources/generated_masks/stage5d18",
        help="Project-relative mask output directory.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    try:
        report = generate_species_masks(output_dir)
    except Exception as exc:
        print("Stage 5D.18 error:", type(exc).__name__ + ": " + str(exc))
        return 2

    print("Forest Manager Stage 5D.18 Deterministic Species Mask Generator:")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if not report.get("verified"):
        return 3
    if not report.get("exclusive_primary_ownership"):
        return 4

    layers = report.get("layers") or []
    if len(layers) != 3:
        return 5

    for layer in layers:
        target = float(layer["target_coverage_percent"])
        achieved = float(layer["achieved_primary_coverage_percent"])
        if abs(target - achieved) > 0.02:
            print("Stage 5D.18 coverage verification failed:", layer["key"])
            return 6

    print("Stage 5D.18 deterministic species mask generation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
