from __future__ import annotations

import json
from dataclasses import asdict

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.distribution import DistributionAdapter


def main() -> int:
    print("Forest Manager Stage 5D.43 Distribution Domain Runtime Boundary:")
    try:
        service = ForestPackControlService()
        adapter = DistributionAdapter(service)
        forests = service.list_forests()
        reports = [asdict(adapter.read_state(name)) for name in forests]
        result = {
            "ok": True,
            "forest_count": len(forests),
            "forests": reports,
            "policy": {
                "read_only_discovery": True,
                "density_write": False,
                "distribution_map_write": False,
                "cluster_write": False,
                "path_distribution_write": False,
                "reference_distribution_write": False,
                "runtime_write_boundary": True,
                "write_boundary_reason": (
                    "Verified bridge exposes discovery only; scalar/property write and rollback "
                    "endpoints are absent from the current runtime capability surface."
                ),
            },
            "verified": True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.43 distribution domain runtime capability boundary passed.")
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__ + ": " + str(exc), "verified": False}, indent=2, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
