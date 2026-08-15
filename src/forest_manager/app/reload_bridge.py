from __future__ import annotations

import json
import sys

from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge


def main() -> int:
    try:
        ping = ensure_current_bridge()
    except Exception as exc:
        print("Automatic bridge reload failed:", type(exc).__name__ + ": " + str(exc))
        return 3

    print("Forest Manager bridge preflight passed.")
    print(json.dumps(ping, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
