from __future__ import annotations

import sys


def render_prompt(prompt: str) -> str:
    return (
        "<|im_start|>User:<image>"
        + prompt
        + "<end_of_utterance>\nAssistant:"
    )


def main() -> int:
    result = render_prompt("Describe the vegetation.")
    print("Forest Manager SmolVLM Chat Prompt:")
    print(result)

    if not result.startswith("<|im_start|>User:<image>"):
        print("Stage 4O.7 chat prompt verification failed.")
        return 1

    if not result.endswith("<end_of_utterance>\nAssistant:"):
        print("Stage 4O.7 chat prompt verification failed.")
        return 2

    print("Stage 4O.7 chat prompt verification passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
