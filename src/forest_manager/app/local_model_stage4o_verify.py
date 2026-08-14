from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from forest_manager.reference_analysis import LocalVisionBundleVerifier


EXPECTED_SHA256 = "d05b567eeaf534e83d375551f068ed57b5f52d37c657197f644af5ef9db091a2"
MODEL_FILE = Path(
    "models/vision/smolvlm-500m-instruct/model.safetensors"
).resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(8 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    bundle = LocalVisionBundleVerifier().inspect()

    payload = bundle.to_dict()
    payload["model_sha256_expected"] = EXPECTED_SHA256
    payload["model_sha256_actual"] = None
    payload["model_sha256_valid"] = False

    if MODEL_FILE.exists():
        actual = sha256_file(MODEL_FILE)
        payload["model_sha256_actual"] = actual
        payload["model_sha256_valid"] = actual == EXPECTED_SHA256

    print("Forest Manager Offline Model Verification:")
    print(json.dumps(payload, indent=2, ensure_ascii=True))

    if not bundle.runtime_ready:
        print("Stage 4O verification: MODEL FILES NOT READY")
        return 2

    if not payload["model_sha256_valid"]:
        print("Stage 4O verification: MODEL HASH FAILED")
        return 3

    print("Stage 4O offline model verification passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
