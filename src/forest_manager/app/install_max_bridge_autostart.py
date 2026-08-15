from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from forest_manager.max_bridge.autostart import (
    BridgeAutoStartError,
    install_bridge_autostart,
    install_detected_bridge_autostart,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install the current Forest Manager bridge into the 3ds Max user startup "
            "folder so the localhost bridge starts automatically after Windows/3ds Max restart."
        )
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2020,
        help="3ds Max year to target when auto-detecting user profiles (default: 2020).",
    )
    parser.add_argument(
        "--max-user-dir",
        default="",
        help=(
            "Optional explicit 3ds Max locale user directory, for example "
            r"C:\Users\NAME\AppData\Local\Autodesk\3dsMax\2020 - 64bit\ENU"
        ),
    )
    args = parser.parse_args()

    try:
        if args.max_user_dir:
            results = [install_bridge_autostart(Path(args.max_user_dir))]
        else:
            results = install_detected_bridge_autostart(year=args.year)
    except BridgeAutoStartError as exc:
        print("Forest Manager bridge autostart install error: " + str(exc))
        return 2
    except Exception as exc:
        print(
            "Forest Manager bridge autostart install error: "
            + type(exc).__name__
            + ": "
            + str(exc)
        )
        return 3

    report = {
        "ok": True,
        "year": args.year,
        "install_count": len(results),
        "installs": [item.to_dict() for item in results],
        "restart_contract": (
            "After installation, ForestManager_Bridge.ms is loaded from the 3ds Max "
            "user scripts/startup directory whenever 3ds Max starts."
        ),
    }
    print("Forest Manager Bridge Auto-Start Install:")
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
