from __future__ import annotations

import json
import sys

from forest_manager.reference_analysis.local_bundle_verifier import (
    LocalVisionBundleVerifier,
)
from forest_manager.reference_analysis.smolvlm500m_local_backend import (
    SmolVLM500MLocalBackend,
)


def _gib(value):
    if value is None:
        return None
    return round(float(value) / (1024 ** 3), 2)


def main() -> int:
    backend = SmolVLM500MLocalBackend()
    bundle = LocalVisionBundleVerifier().inspect()
    payload = bundle.to_dict()

    hardware = payload["hardware"]
    hardware["total_ram_gib"] = _gib(hardware.get("total_ram_bytes"))
    hardware["free_disk_gib"] = _gib(hardware.get("free_disk_bytes"))
    hardware["cuda_total_vram_gib"] = _gib(
        hardware.get("cuda_total_vram_bytes")
    )

    payload["active_model"] = {
        "id": "smolvlm-500m-instruct",
        "path": str(backend.config.model_dir),
        "device_policy": "cuda_if_available_else_cpu",
        "cpu_dtype": "float32",
        "runtime_network": False,
    }

    print("Forest Manager Stage 4N Local Vision:")
    print(json.dumps(payload, indent=2, ensure_ascii=True))

    if bundle.runtime_ready:
        print("Stage 4N local vision readiness passed.")
        return 0

    print("Stage 4N local vision readiness: NOT READY")
    print("Blockers: " + ", ".join(bundle.blockers))
    return 2


if __name__ == "__main__":
    sys.exit(main())
