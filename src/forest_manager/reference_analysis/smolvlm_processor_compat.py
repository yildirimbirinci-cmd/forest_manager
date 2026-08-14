from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LocalProcessorMetadataError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LocalProcessorMetadataError(
            f"Required processor metadata file is missing: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise LocalProcessorMetadataError(
            f"Processor metadata is invalid JSON: {path}"
        ) from exc

    if not isinstance(payload, dict):
        raise LocalProcessorMetadataError(
            f"Processor metadata must be a JSON object: {path}"
        )
    return payload


def _write_json_if_changed(path: Path, payload: dict[str, Any], changed: bool) -> bool:
    if not changed:
        return False

    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return True


def ensure_smolvlm_processor_metadata(model_dir: Path | str) -> dict[str, Any]:
    """
    Repair only local metadata required by newer Transformers versions.

    The model weights are never modified.
    No network request is performed.
    """
    root = Path(model_dir).resolve()
    preprocessor_path = root / "preprocessor_config.json"
    processor_path = root / "processor_config.json"

    preprocessor = _load_json(preprocessor_path)
    processor = _load_json(processor_path)

    preprocessor_changed = False
    processor_changed = False

    if not str(preprocessor.get("image_processor_type") or "").strip():
        preprocessor["image_processor_type"] = "Idefics3ImageProcessor"
        preprocessor_changed = True

    if not str(preprocessor.get("processor_class") or "").strip():
        preprocessor["processor_class"] = "Idefics3Processor"
        preprocessor_changed = True

    if not str(processor.get("processor_class") or "").strip():
        processor["processor_class"] = "Idefics3Processor"
        processor_changed = True

    _write_json_if_changed(
        preprocessor_path,
        preprocessor,
        preprocessor_changed,
    )
    _write_json_if_changed(
        processor_path,
        processor,
        processor_changed,
    )

    return {
        "model_dir": str(root),
        "preprocessor_config": str(preprocessor_path),
        "processor_config": str(processor_path),
        "image_processor_type": preprocessor.get("image_processor_type"),
        "preprocessor_processor_class": preprocessor.get("processor_class"),
        "processor_class": processor.get("processor_class"),
        "preprocessor_changed": preprocessor_changed,
        "processor_changed": processor_changed,
        "verified": (
            preprocessor.get("image_processor_type") == "Idefics3ImageProcessor"
            and preprocessor.get("processor_class") == "Idefics3Processor"
            and processor.get("processor_class") == "Idefics3Processor"
        ),
    }
