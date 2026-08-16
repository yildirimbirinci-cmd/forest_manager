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
        cluster = snapshot.get("controls", {}).get("cluster_character", {})
        payload = {
            "ok": True,
            "forest_name": snapshot.get("forest_name"),
            "scene_units": snapshot.get("scene_units", {}),
            "cluster_character": cluster,
            "read_only": True,
            "policy": {
                "read_only_probe": True,
                "no_cluster_raw_values_guessed": True,
                "existing_runtime_values_only": True,
                "cluster_character_requires_runtime_calibration": True,
            },
            "verified": True,
        }
    print("Forest Manager Stage 7.7 Cluster Character Calibration Probe:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
