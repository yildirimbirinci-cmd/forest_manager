# Stage 4I - Reference Image Analysis Pipeline

Stage 4I creates the product-facing boundary for reference images.

The important architectural rule is that Forest Manager does not pretend to
understand plant species before a real semantic vision analyzer is connected.

Current Stage 4I behavior:

1. Accept a PNG/JPG/JPEG reference image.
2. Validate that the file exists and is readable.
3. Read width, height, aspect ratio, orientation, and file size.
4. Return a typed `ReferenceAnalysisResult`.
5. Expose a `ReferencePlanBuilder` that will convert future semantic plant
   suggestions into the already verified `CompositionPlan`.
6. Refuse automatic T2 species selection when semantic suggestions are absent.

This means the future GUI can already use one stable flow:

    Reference Image
        -> ReferenceImageAnalyzer
        -> ReferenceAnalysisResult
        -> ReferencePlanBuilder
        -> CompositionPlan
        -> T2 Asset Resolution
        -> Forest Pack

The next stage can replace/extend only the analyzer with real image semantics.

## Manual acceptance

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.reference_image_stage4i_smoke "C:\path\to\reference.jpg"

Expected:

    Stage 4I reference-image pipeline acceptance passed.

No 3ds Max scene changes are made by this test.
