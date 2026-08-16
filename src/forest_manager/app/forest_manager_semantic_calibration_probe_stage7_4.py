from __future__ import annotations

import json

from forest_manager.ui.controller import ForestManagerUIController


def main() -> int:
    controller = ForestManagerUIController()
    state = controller.refresh_scene(prefer_max_selection=True)
    if not state.bridge_online or state.error:
        payload = {
            "ok": False,
            "error": state.error or state.status,
            "verified": False,
        }
    else:
        snapshot = controller.semantic_calibration_snapshot()
        payload = {
            "ok": True,
            **snapshot,
            "policy": {
                "read_only_probe": True,
                "no_semantic_raw_values_guessed": True,
                "naturalness_requires_runtime_calibration": True,
                "variation_requires_runtime_calibration": True,
            },
            "verified": True,
        }
    print("Forest Manager Stage 7.4 Semantic Calibration Probe:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
