from __future__ import annotations

from pathlib import Path
import sys


def render_prompt(prompt: str) -> str:
    return "User:<image>" + prompt + "<end_of_utterance>\nAssistant:"


def main() -> int:
    sample = render_prompt("Describe the planting composition.")
    expected = (
        "User:<image>Describe the planting composition."
        "<end_of_utterance>\nAssistant:"
    )

    print("Forest Manager SmolVLM Prompt:")
    print(sample)

    if sample != expected:
        print("Stage 4O.4 direct prompt rendering failed.")
        return 1

    print("Stage 4O.4 direct prompt rendering passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
