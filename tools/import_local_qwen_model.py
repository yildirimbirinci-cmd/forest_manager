from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys


REQUIRED_CONFIG = "config.json"
TARGET = Path("models/vision/qwen2.5-vl-3b-instruct")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import an already-downloaded local Qwen2.5-VL model."
    )
    parser.add_argument("source", help="Existing local model directory.")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    if not source.exists() or not source.is_dir():
        print("Source model directory does not exist.")
        return 1

    if not (source / REQUIRED_CONFIG).exists():
        print("Source is not a complete model directory: config.json missing.")
        return 2

    TARGET.mkdir(parents=True, exist_ok=True)

    for item in source.iterdir():
        destination = TARGET / item.name
        if item.is_dir():
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)

    print("Local Qwen model imported to:", TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
