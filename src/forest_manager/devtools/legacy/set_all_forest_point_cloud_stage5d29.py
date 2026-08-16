from __future__ import annotations

import json

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


def main() -> int:
    print("Forest Manager Stage 5D.29 Set All Forest Viewports to Points Cloud:")
    ensure_current_bridge()
    response = send_command("SET_ALL_FOREST_POINT_CLOUD")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        raise RuntimeError(response.get("error") or "SET_ALL_FOREST_POINT_CLOUD failed.")

    data = response.get("data") or {}
    if data.get("viewport_display") != "points_cloud":
        raise RuntimeError("Forest viewport display mode was not reported as Points Cloud.")
    if int(data.get("vmesh", -1)) != 3:
        raise RuntimeError("Forest viewport vmesh is not 3 (Points Cloud).")
    if data.get("render_settings_changed") is not False:
        raise RuntimeError("Render settings must remain unchanged.")
    if not data.get("verified"):
        raise RuntimeError("Points Cloud verification failed.")

    print("All Forest Pack viewport display modes are now Points Cloud. Render settings were preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
