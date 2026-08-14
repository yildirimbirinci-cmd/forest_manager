from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .local_backend import (
    LocalVisionBackendError,
    LocalVisionModelConfig,
)


class TransformersLocalVisionBackend:
    """
    Offline-only local vision backend.

    The model and processor are loaded exclusively from `model_dir` with
    `local_files_only=True`. No model download or network fallback is allowed.
    """

    def __init__(self, config: LocalVisionModelConfig | None = None):
        self.config = config or LocalVisionModelConfig.default()

    @property
    def name(self) -> str:
        return "transformers_local_vision"

    def is_available(self) -> bool:
        try:
            self.config.validate()
            import torch  # noqa: F401
            import transformers  # noqa: F401
        except (ImportError, LocalVisionBackendError):
            return False
        return True

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].lstrip()

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end < start:
            raise LocalVisionBackendError(
                "Local vision model did not return a JSON object."
            )

        try:
            payload = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as exc:
            raise LocalVisionBackendError(
                "Local vision model returned invalid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise LocalVisionBackendError(
                "Local vision output must be a JSON object."
            )
        return payload

    def analyze(self, image_path: str, prompt: str) -> dict[str, Any]:
        self.config.validate()

        try:
            import torch
            from PIL import Image
            from transformers import AutoProcessor
        except ImportError as exc:
            raise LocalVisionBackendError(
                "Local vision dependencies are missing. "
                "Forest Manager must bundle torch, Pillow, and transformers."
            ) from exc

        model_dir = str(self.config.model_dir)

        try:
            processor = AutoProcessor.from_pretrained(
                model_dir,
                local_files_only=True,
                trust_remote_code=False,
            )
        except Exception as exc:
            raise LocalVisionBackendError(
                "Could not load the local vision processor from models/vision."
            ) from exc

        model = None
        model_errors: list[str] = []

        # Prefer the generic image-text-to-text class when available.
        try:
            from transformers import AutoModelForImageTextToText
            model = AutoModelForImageTextToText.from_pretrained(
                model_dir,
                local_files_only=True,
                trust_remote_code=False,
                torch_dtype="auto",
            )
        except Exception as exc:
            model_errors.append(str(exc))

        if model is None:
            try:
                from transformers import AutoModelForVision2Seq
                model = AutoModelForVision2Seq.from_pretrained(
                    model_dir,
                    local_files_only=True,
                    trust_remote_code=False,
                    torch_dtype="auto",
                )
            except Exception as exc:
                model_errors.append(str(exc))

        if model is None:
            raise LocalVisionBackendError(
                "Could not load a supported local vision-language model. "
                + " | ".join(model_errors[-2:])
            )

        image = Image.open(image_path).convert("RGB")

        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image"},
                        {"type": "text", "text": prompt},
                    ],
                }
            ]

            if hasattr(processor, "apply_chat_template"):
                rendered = processor.apply_chat_template(
                    messages,
                    add_generation_prompt=True,
                    tokenize=False,
                )
                inputs = processor(
                    text=[rendered],
                    images=[image],
                    return_tensors="pt",
                )
            else:
                inputs = processor(
                    text=[prompt],
                    images=[image],
                    return_tensors="pt",
                )

            if hasattr(model, "device"):
                inputs = {
                    key: value.to(model.device) if hasattr(value, "to") else value
                    for key, value in inputs.items()
                }

            with torch.inference_mode():
                generated = model.generate(
                    **inputs,
                    max_new_tokens=self.config.max_new_tokens,
                    do_sample=False,
                )

            text = processor.batch_decode(
                generated,
                skip_special_tokens=True,
            )[0]
        finally:
            image.close()

        return self._extract_json(text)
