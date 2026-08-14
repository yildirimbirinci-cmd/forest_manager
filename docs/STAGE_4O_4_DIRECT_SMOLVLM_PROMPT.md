# Stage 4O.4 - Direct SmolVLM Prompt Rendering

The direct Idefics3 processor now constructs successfully, but the manually
constructed processor has no registered `chat_template`, causing
`apply_chat_template()` to fail.

The official SmolVLM-500M-Instruct chat template renders a single image + text
user turn as:

    User:<image>{prompt}<end_of_utterance>
    Assistant:

Stage 4O.4 renders that prompt directly and passes the text plus image into the
local Idefics3 processor.

No network access is introduced.

## Quick check

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.smolvlm_stage4o4_prompt

Expected:

    Stage 4O.4 direct prompt rendering passed.

## Real inference

    python -m forest_manager.app.local_vision_stage4k "C:\Users\yildi\Desktop\ref\ref01.png"
