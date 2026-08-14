# Stage 4O.7 - SmolVLM Chat Prompt Boundary Fix

Observed output after successful image inference was a repetition of the semantic
instruction instead of an assistant answer.

Root cause:
the manually rendered Stage 4O.4 prompt omitted the `<|im_start|>` token that is
present at the beginning of the official SmolVLM chat template.

Runtime prompt is now:

    <|im_start|>User:<image>{prompt}<end_of_utterance>
    Assistant:

The semantic request is also shorter for the 500M model.

Generation remains deterministic and is capped at 192 new tokens to reduce CPU
latency.

No network access is introduced.

## Prompt verification

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.smolvlm_stage4o7_chat_prompt

## Real inference

    python -m forest_manager.app.local_vision_stage4k "C:\Users\yildi\Desktop\ref\ref01.png"
