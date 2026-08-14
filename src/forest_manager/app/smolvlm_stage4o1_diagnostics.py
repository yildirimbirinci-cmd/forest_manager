from __future__ import annotations

import json
from pathlib import Path
import platform
import sys


MODEL_DIR = Path("models/vision/smolvlm-500m-instruct").resolve()


def _version(module_name: str) -> str | None:
    try:
        module = __import__(module_name)
        return str(getattr(module, "__version__", "unknown"))
    except Exception:
        return None


def main() -> int:
    payload = {
        "python": platform.python_version(),
        "torch": _version("torch"),
        "transformers": _version("transformers"),
        "pillow": _version("PIL"),
        "model_dir": str(MODEL_DIR),
        "config_exists": (MODEL_DIR / "config.json").exists(),
        "model_exists": (MODEL_DIR / "model.safetensors").exists(),
        "processor_exists": (
            (MODEL_DIR / "processor_config.json").exists()
            or (MODEL_DIR / "preprocessor_config.json").exists()
        ),
        "architectures": None,
        "model_type": None,
    }

    config_path = MODEL_DIR / "config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            payload["architectures"] = config.get("architectures")
            payload["model_type"] = config.get("model_type")
        except Exception as exc:
            payload["config_error"] = type(exc).__name__ + ": " + str(exc)

    print("Forest Manager SmolVLM Diagnostics:")
    print(json.dumps(payload, indent=2, ensure_ascii=True))

    try:
        from forest_manager.reference_analysis.smolvlm500m_local_backend import (
            SmolVLM500MLocalBackend,
        )

        backend = SmolVLM500MLocalBackend()
        print("backend_available:", backend.is_available())
    except Exception as exc:
        print(
            "backend_diagnostic_error:",
            type(exc).__name__ + ": " + str(exc),
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
