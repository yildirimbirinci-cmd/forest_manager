from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys


TARGET = Path("models/vision/smolvlm-500m-instruct")
REQUIRED = ("config.json",)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import an existing local SmolVLM-500M-Instruct directory."
    )
    parser.add_argument("source", help="Existing local model directory.")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    if not source.exists() or not source.is_dir():
        print("Source model directory does not exist.")
        return 1

    for required in REQUIRED:
        if not (source / required).exists():
            print("Source model directory is incomplete:", required)
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

    print("Local SmolVLM model imported to:", TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
