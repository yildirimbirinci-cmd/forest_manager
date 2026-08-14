from __future__ import annotations

import json
from pathlib import Path
import sys


MODEL_DIR = Path("models/vision/smolvlm-500m-instruct").resolve()


def main() -> int:
    try:
        from transformers import (
            AutoTokenizer,
            Idefics3ImageProcessor,
            Idefics3Processor,
        )

        image_processor = Idefics3ImageProcessor.from_pretrained(
            str(MODEL_DIR),
            local_files_only=True,
        )
        tokenizer = AutoTokenizer.from_pretrained(
            str(MODEL_DIR),
            local_files_only=True,
            trust_remote_code=False,
        )

        processor_config = {}
        processor_config_path = MODEL_DIR / "processor_config.json"
        if processor_config_path.exists():
            processor_config = json.loads(
                processor_config_path.read_text(encoding="utf-8")
            )

        image_seq_len = int(processor_config.get("image_seq_len", 64))

        processor = Idefics3Processor(
            image_processor=image_processor,
            tokenizer=tokenizer,
            image_seq_len=image_seq_len,
        )

        print("Forest Manager Direct Processor Diagnostics:")
        print(
            json.dumps(
                {
                    "image_processor_class": type(image_processor).__name__,
                    "tokenizer_class": type(tokenizer).__name__,
                    "processor_class": type(processor).__name__,
                    "image_seq_len": image_seq_len,
                    "verified": True,
                },
                indent=2,
                ensure_ascii=True,
            )
        )
        print("Stage 4O.3 direct processor construction passed.")
        return 0

    except Exception as exc:
        print(
            "Stage 4O.3 direct processor construction failed:",
            type(exc).__name__ + ": " + str(exc),
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
