from __future__ import annotations

import json

from forest_manager.forest_control.plant_group_execution import execute_plant_group_manifest
from forest_manager.max_bridge.runtime_bridge import read_plant_group_manifest


def main() -> int:
    manifest = read_plant_group_manifest()
    result = execute_plant_group_manifest(manifest)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("verified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
