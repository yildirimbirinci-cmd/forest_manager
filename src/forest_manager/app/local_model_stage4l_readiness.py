from __future__ import annotations

import json
import sys

from forest_manager.reference_analysis import (
    LocalModelVerifier,
    Qwen25VLLocalBackend,
)


def main() -> int:
    backend = Qwen25VLLocalBackend()
    result = LocalModelVerifier(backend.config.model_dir).inspect()

    print("Local Vision Model Readiness:")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=True))

    if not result.ready:
        print("Stage 4L model readiness: NOT READY")
        print(
            "Place the complete Qwen2.5-VL-3B-Instruct model files under: "
            + result.model_dir
        )
        return 2

    print("Stage 4L local model readiness passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
