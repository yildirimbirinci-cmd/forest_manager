from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


REPO_ID = "HuggingFaceTB/SmolVLM-500M-Instruct"
REVISION = "e2d212496dbdaa5d0e540b14645c2a0a77eece6e"
MODEL_SHA256 = "d05b567eeaf534e83d375551f068ed57b5f52d37c657197f644af5ef9db091a2"
TARGET = Path("models/vision/smolvlm-500m-instruct").resolve()

ALLOW_PATTERNS = [
    "README.md",
    "LICENSE*",
    "added_tokens.json",
    "chat_template.json",
    "config.json",
    "generation_config.json",
    "merges.txt",
    "model.safetensors",
    "preprocessor_config.json",
    "processor_config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
]

IGNORE_PATTERNS = [
    "onnx/*",
    "*.onnx",
]


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
    parser = argparse.ArgumentParser(
        description=(
            "One-time developer bootstrap for the Forest Manager local vision model. "
            "The application runtime itself does not use the network."
        )
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download files even if the target already appears complete.",
    )
    args = parser.parse_args()

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("huggingface_hub is missing.")
        print("It must be present only for this one-time developer bootstrap.")
        return 10

    TARGET.mkdir(parents=True, exist_ok=True)

    model_file = TARGET / "model.safetensors"
    if model_file.exists() and not args.force:
        current_hash = sha256_file(model_file)
        if current_hash == MODEL_SHA256:
            print("Pinned SmolVLM model already exists and hash is valid.")
            print("Target:", TARGET)
            return 0
        print("Existing model hash does not match the pinned revision.")
        print("Use --force to replace it.")
        return 11

    print("Downloading pinned Forest Manager local vision model...")
    print("Repository:", REPO_ID)
    print("Revision:", REVISION)
    print("Target:", TARGET)
    print("Runtime network policy remains OFFLINE.")

    snapshot_download(
        repo_id=REPO_ID,
        revision=REVISION,
        local_dir=str(TARGET),
        allow_patterns=ALLOW_PATTERNS,
        ignore_patterns=IGNORE_PATTERNS,
    )

    if not model_file.exists():
        print("Bootstrap failed: model.safetensors is missing.")
        return 12

    current_hash = sha256_file(model_file)
    if current_hash != MODEL_SHA256:
        print("Bootstrap failed: model.safetensors SHA256 mismatch.")
        print("Expected:", MODEL_SHA256)
        print("Actual:", current_hash)
        return 13

    manifest = TARGET / "forest_manager_model.json"
    if not manifest.exists():
        print("Warning: Forest Manager model manifest is missing.")
        return 14

    required = [
        "config.json",
        "model.safetensors",
        "preprocessor_config.json",
        "processor_config.json",
        "tokenizer.json",
    ]
    missing = [name for name in required if not (TARGET / name).exists()]
    if missing:
        print("Bootstrap failed. Missing:", ", ".join(missing))
        return 15

    preprocessor_path = TARGET / "preprocessor_config.json"
    processor_path = TARGET / "processor_config.json"

    try:
        preprocessor = json.loads(preprocessor_path.read_text(encoding="utf-8"))
        processor = json.loads(processor_path.read_text(encoding="utf-8"))

        preprocessor.setdefault(
            "image_processor_type",
            "Idefics3ImageProcessor",
        )
        preprocessor.setdefault(
            "processor_class",
            "Idefics3Processor",
        )
        processor.setdefault(
            "processor_class",
            "Idefics3Processor",
        )

        preprocessor_path.write_text(
            json.dumps(preprocessor, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        processor_path.write_text(
            json.dumps(processor, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        print(
            "Bootstrap failed while normalizing processor metadata:",
            type(exc).__name__ + ": " + str(exc),
        )
        return 16

    print("SmolVLM bootstrap completed and SHA256 verified.")
    print("Processor metadata compatibility normalized.")
    print("The model is now available for offline Forest Manager runtime.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
