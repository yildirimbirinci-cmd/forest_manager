from __future__ import annotations

import json
import sys

from forest_manager.reference_analysis import LocalVisionBundleVerifier


def _gib(value):
    if value is None:
        return None
    return round(float(value) / (1024 ** 3), 2)


def main() -> int:
    result = LocalVisionBundleVerifier().inspect()
    payload = result.to_dict()

    hardware = payload["hardware"]
    model = payload["model"]

    hardware["total_ram_gib"] = _gib(hardware.get("total_ram_bytes"))
    hardware["free_disk_gib"] = _gib(hardware.get("free_disk_bytes"))
    hardware["cuda_total_vram_gib"] = _gib(
        hardware.get("cuda_total_vram_bytes")
    )

    print("Forest Manager Local Vision Readiness:")
    print(json.dumps(payload, indent=2, ensure_ascii=True))

    if result.runtime_ready:
        print("Stage 4M local vision bundle readiness passed.")
        return 0

    print("Stage 4M local vision bundle readiness: NOT READY")
    print("Blockers: " + ", ".join(result.blockers))
    return 2


if __name__ == "__main__":
    sys.exit(main())
