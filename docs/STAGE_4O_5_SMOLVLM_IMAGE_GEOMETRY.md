# Stage 4O.5 - SmolVLM Image Geometry Fix

Observed runtime failure:

    RuntimeError: shape '[17, 22, 5, 3072]' is invalid ...

The failure occurs inside the Idefics3 pixel-shuffle connector and indicates
that the image feature grid does not match the model scale factor.

SmolVLM-500M uses a 512-based vision input geometry. The backend now constructs
the image processor explicitly with:

    size={"longest_edge": 2048}
    max_image_size={"longest_edge": 512}
    do_image_splitting=True

This avoids stale processor defaults from the pinned snapshot.

A pre-generation guard also verifies that the generated pixel tensor has
dimensions divisible by 512.

## Geometry-only verification

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.smolvlm_stage4o5_image_geometry "C:\Users\yildi\Desktop\ref\ref01.png"

Expected:

    Stage 4O.5 image geometry verification passed.

## Real inference

    python -m forest_manager.app.local_vision_stage4k "C:\Users\yildi\Desktop\ref\ref01.png"
