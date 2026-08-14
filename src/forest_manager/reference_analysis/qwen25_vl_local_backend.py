from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .local_backend import LocalVisionBackendError, LocalVisionModelConfig
from .local_model_verifier import LocalModelVerifier


class Qwen25VLLocalBackend:
    MODEL_SUBDIR = Path("models/vision/qwen2.5-vl-3b-instruct")

    def __init__(self, config: LocalVisionModelConfig | None = None):
        self.config = config or LocalVisionModelConfig(
            model_dir=self.MODEL_SUBDIR.resolve(),
            backend="qwen2.5-vl",
            max_new_tokens=768,
        )

    @property
    def name(self) -> str:
        return "qwen2.5-vl-3b-local"

    def is_available(self) -> bool:
        return LocalModelVerifier(self.config.model_dir).inspect().ready

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
                "Qwen local vision output did not contain a JSON object."
            )

        try:
            payload = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as exc:
            raise LocalVisionBackendError(
                "Qwen local vision output contained invalid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise LocalVisionBackendError(
                "Qwen local vision output must be a JSON object."
            )

        return payload

    @staticmethod
    def _select_device(torch_module) -> str:
        if torch_module.cuda.is_available():
            return "cuda"
        return "cpu"

    def analyze(self, image_path: str, prompt: str) -> dict[str, Any]:
        readiness = LocalModelVerifier(self.config.model_dir).inspect()
        if not readiness.ready:
            raise LocalVisionBackendError(
                "Qwen local vision model is not ready under "
                f"{self.config.model_dir}"
            )

        # Hard offline guard. Even accidental Hugging Face calls must fail locally
        # instead of using the network.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

        try:
            import torch
            from PIL import Image
            from transformers import (
                AutoProcessor,
                Qwen2_5_VLForConditionalGeneration,
            )
        except ImportError as exc:
            raise LocalVisionBackendError(
                "Bundled Qwen local vision dependencies are incomplete."
            ) from exc

        model_dir = str(self.config.model_dir)
        device = self._select_device(torch)

        try:
            processor = AutoProcessor.from_pretrained(
                model_dir,
                local_files_only=True,
                trust_remote_code=False,
            )

            model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                model_dir,
                local_files_only=True,
                trust_remote_code=False,
                torch_dtype="auto",
                device_map="auto",
            )
        except Exception as exc:
            raise LocalVisionBackendError(
                "Could not load the bundled Qwen2.5-VL model locally."
            ) from exc

        image = Image.open(image_path).convert("RGB")

        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": image},
                        {"type": "text", "text": prompt},
                    ],
                }
            ]

            try:
                inputs = processor.apply_chat_template(
                    messages,
                    tokenize=True,
                    add_generation_prompt=True,
                    return_dict=True,
                    return_tensors="pt",
                )
            except Exception:
                text = processor.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
                inputs = processor(
                    text=[text],
                    images=[image],
                    padding=True,
                    return_tensors="pt",
                )

            target_device = getattr(model, "device", None)
            if target_device is not None:
                if hasattr(inputs, "to"):
                    inputs = inputs.to(target_device)
                elif isinstance(inputs, dict):
                    inputs = {
                        key: value.to(target_device) if hasattr(value, "to") else value
                        for key, value in inputs.items()
                    }

            input_ids = inputs["input_ids"]

            with torch.inference_mode():
                generated = model.generate(
                    **inputs,
                    max_new_tokens=self.config.max_new_tokens,
                    do_sample=False,
                )

            trimmed = [
                output_ids[len(input_row):]
                for input_row, output_ids in zip(input_ids, generated)
            ]

            text = processor.batch_decode(
                trimmed,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )[0]
        finally:
            image.close()

        return self._extract_json(text)
