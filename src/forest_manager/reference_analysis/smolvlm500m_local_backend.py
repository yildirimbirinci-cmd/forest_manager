from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .local_backend import LocalVisionBackendError, LocalVisionModelConfig
from .local_model_verifier import LocalModelVerifier
from .local_semantic_parser import (
    LocalSemanticParseError,
    parse_local_semantic_output,
)
from .smolvlm_processor_compat import (
    LocalProcessorMetadataError,
    ensure_smolvlm_processor_metadata,
)


class SmolVLM500MLocalBackend:
    MODEL_SUBDIR = Path("models/vision/smolvlm-500m-instruct")

    def __init__(self, config: LocalVisionModelConfig | None = None):
        self.config = config or LocalVisionModelConfig(
            model_dir=self.MODEL_SUBDIR.resolve(),
            backend="smolvlm-500m",
            max_new_tokens=512,
        )

    @property
    def name(self) -> str:
        return "smolvlm-500m-local"

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
                "SmolVLM output did not contain a JSON object."
            )

        try:
            payload = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as exc:
            raise LocalVisionBackendError(
                "SmolVLM output contained invalid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise LocalVisionBackendError(
                "SmolVLM output must be a JSON object."
            )
        return payload

    def analyze(self, image_path: str, prompt: str) -> dict[str, Any]:
        readiness = LocalModelVerifier(self.config.model_dir).inspect()
        if not readiness.ready:
            raise LocalVisionBackendError(
                "SmolVLM local model is not ready under "
                f"{self.config.model_dir}"
            )

        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

        try:
            import torch
            from PIL import Image
            from transformers import (
                AutoTokenizer,
                Idefics3ImageProcessor,
                Idefics3Processor,
            )
        except ImportError as exc:
            raise LocalVisionBackendError(
                "Bundled SmolVLM dependencies are incomplete."
            ) from exc

        try:
            ensure_smolvlm_processor_metadata(self.config.model_dir)
        except LocalProcessorMetadataError as exc:
            raise LocalVisionBackendError(str(exc)) from exc

        model_dir = str(self.config.model_dir)
        device = "cuda" if torch.cuda.is_available() else "cpu"

        # On CPU, float32 is the conservative compatibility default.
        # On CUDA, bfloat16 can reduce memory usage when supported.
        dtype = torch.float32
        if device == "cuda" and torch.cuda.is_bf16_supported():
            dtype = torch.bfloat16

        try:
            try:
                # SmolVLM-500M uses a 512-based image geometry.
                # Build the processor explicitly instead of inheriting stale
                # snapshot defaults that are incompatible with current
                # Transformers pixel-shuffle expectations.
                image_processor = Idefics3ImageProcessor(
                    size={"longest_edge": 2048},
                    max_image_size={"longest_edge": 512},
                    do_resize=True,
                    do_rescale=True,
                    do_normalize=True,
                    do_convert_rgb=True,
                    do_image_splitting=True,
                    do_pad=True,
                )
                tokenizer = AutoTokenizer.from_pretrained(
                    model_dir,
                    local_files_only=True,
                    trust_remote_code=False,
                )

                processor_config_path = self.config.model_dir / "processor_config.json"
                image_seq_len = 64
                if processor_config_path.exists():
                    try:
                        processor_payload = json.loads(
                            processor_config_path.read_text(encoding="utf-8")
                        )
                        image_seq_len = int(
                            processor_payload.get("image_seq_len", image_seq_len)
                        )
                    except Exception:
                        pass

                chat_template = None
                chat_template_path = self.config.model_dir / "chat_template.json"
                if chat_template_path.exists():
                    try:
                        chat_payload = json.loads(
                            chat_template_path.read_text(encoding="utf-8")
                        )
                        if isinstance(chat_payload, str):
                            chat_template = chat_payload
                        elif isinstance(chat_payload, dict):
                            candidate = chat_payload.get("chat_template")
                            if isinstance(candidate, str):
                                chat_template = candidate
                    except Exception:
                        pass

                processor = Idefics3Processor(
                    image_processor=image_processor,
                    tokenizer=tokenizer,
                    image_seq_len=image_seq_len,
                    chat_template=chat_template,
                )
            except Exception as exc:
                raise LocalVisionBackendError(
                    "Could not initialize local Idefics3 processor. "
                    + type(exc).__name__
                    + ": "
                    + str(exc)
                ) from exc

            load_errors: list[str] = []
            model = None

            try:
                from transformers import AutoModelForVision2Seq

                model = AutoModelForVision2Seq.from_pretrained(
                    model_dir,
                    local_files_only=True,
                    trust_remote_code=False,
                    torch_dtype=dtype,
                    _attn_implementation="eager",
                )
            except Exception as exc:
                load_errors.append(
                    "AutoModelForVision2Seq: "
                    + type(exc).__name__
                    + ": "
                    + str(exc)
                )

            if model is None:
                try:
                    from transformers import Idefics3ForConditionalGeneration

                    model = Idefics3ForConditionalGeneration.from_pretrained(
                        model_dir,
                        local_files_only=True,
                        trust_remote_code=False,
                        torch_dtype=dtype,
                        _attn_implementation="eager",
                    )
                except Exception as exc:
                    load_errors.append(
                        "Idefics3ForConditionalGeneration: "
                        + type(exc).__name__
                        + ": "
                        + str(exc)
                    )

            if model is None:
                raise LocalVisionBackendError(
                    "Could not load bundled SmolVLM locally. "
                    + " | ".join(load_errors)
                )

            model = model.to(device)
        except LocalVisionBackendError:
            raise
        except Exception as exc:
            raise LocalVisionBackendError(
                "Could not initialize bundled SmolVLM locally. "
                + type(exc).__name__
                + ": "
                + str(exc)
            ) from exc

        image = Image.open(image_path).convert("RGB")
        try:
            # Render the official SmolVLM single-turn chat template directly.
            # This avoids ProcessorMixin chat-template lookup incompatibilities
            # while preserving the model's expected prompt format.
            rendered = (
                "<|im_start|>User:<image>"
                + prompt
                + "<end_of_utterance>\nAssistant:"
            )

            inputs = processor(
                text=[rendered],
                images=[image],
                return_tensors="pt",
            ).to(device)

            input_length = inputs["input_ids"].shape[-1]

            pixel_values = inputs.get("pixel_values")
            if pixel_values is None:
                raise LocalVisionBackendError(
                    "SmolVLM processor did not produce pixel_values."
                )

            pixel_height = int(pixel_values.shape[-2])
            pixel_width = int(pixel_values.shape[-1])

            if pixel_height % 512 != 0 or pixel_width % 512 != 0:
                raise LocalVisionBackendError(
                    "SmolVLM image geometry is invalid before generation: "
                    f"{pixel_width}x{pixel_height}. "
                    "Both dimensions must be divisible by 512."
                )

            with torch.inference_mode():
                generated_ids = model.generate(
                    **inputs,
                    max_new_tokens=min(self.config.max_new_tokens, 192),
                    do_sample=False,
                    repetition_penalty=1.03,
                )

            generated_only = generated_ids[:, input_length:]
            text = processor.batch_decode(
                generated_only,
                skip_special_tokens=True,
            )[0]
        finally:
            image.close()

        try:
            return parse_local_semantic_output(text)
        except LocalSemanticParseError as exc:
            raise LocalVisionBackendError(str(exc)) from exc
