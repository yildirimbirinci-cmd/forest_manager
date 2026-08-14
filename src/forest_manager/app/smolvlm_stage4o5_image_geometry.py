from __future__ import annotations

import json
from pathlib import Path
import sys

from PIL import Image
from transformers import AutoTokenizer, Idefics3ImageProcessor, Idefics3Processor


MODEL_DIR = Path("models/vision/smolvlm-500m-instruct").resolve()


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python -m forest_manager.app.smolvlm_stage4o5_image_geometry IMAGE")
        return 1

    image_path = Path(sys.argv[1]).resolve()
    if not image_path.exists():
        print("Image does not exist:", image_path)
        return 2

    try:
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
            str(MODEL_DIR),
            local_files_only=True,
            trust_remote_code=False,
        )

        processor = Idefics3Processor(
            image_processor=image_processor,
            tokenizer=tokenizer,
            image_seq_len=64,
        )

        image = Image.open(image_path).convert("RGB")
        try:
            rendered = (
                "User:<image>Describe the planting composition."
                "<end_of_utterance>\nAssistant:"
            )
            inputs = processor(
                text=[rendered],
                images=[image],
                return_tensors="pt",
            )
        finally:
            image.close()

        pixels = inputs["pixel_values"]
        height = int(pixels.shape[-2])
        width = int(pixels.shape[-1])

        result = {
            "pixel_values_shape": list(pixels.shape),
            "pixel_width": width,
            "pixel_height": height,
            "width_divisible_by_512": width % 512 == 0,
            "height_divisible_by_512": height % 512 == 0,
            "verified": width % 512 == 0 and height % 512 == 0,
        }

        print("Forest Manager SmolVLM Image Geometry:")
        print(json.dumps(result, indent=2, ensure_ascii=True))

        if not result["verified"]:
            print("Stage 4O.5 image geometry verification failed.")
            return 3

        print("Stage 4O.5 image geometry verification passed.")
        return 0

    except Exception as exc:
        print(
            "Stage 4O.5 image geometry error:",
            type(exc).__name__ + ": " + str(exc),
        )
        return 4


if __name__ == "__main__":
    sys.exit(main())
