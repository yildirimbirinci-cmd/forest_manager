from __future__ import annotations

import argparse
import json
import sys

from forest_manager.reference_analysis import (
    JsonSemanticVisionProvider,
    ReferenceImageAnalyzer,
    ReferenceImageError,
    SemanticCompositionPlanBuilder,
    SemanticPlanError,
    SemanticVisionError,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the Stage 4J semantic vision provider contract."
    )
    parser.add_argument("image", help="Reference PNG/JPG/JPEG image.")
    parser.add_argument(
        "--semantic-json",
        default="config/semantic_analysis_stage4j.json",
    )
    args = parser.parse_args()

    try:
        structural = ReferenceImageAnalyzer().analyze(args.image)
        provider = JsonSemanticVisionProvider(args.semantic_json)

        semantic = provider.analyze_image(
            structural.image.path,
            width=structural.image.width,
            height=structural.image.height,
            orientation=structural.image.orientation,
        )

        plan = SemanticCompositionPlanBuilder().build(
            semantic,
            image_filename=structural.image.filename,
        )

        output = {
            "image": structural.image.to_dict(),
            "semantic": semantic.to_dict(),
            "composition_plan": {
                "name": plan.name,
                "items": [
                    {
                        "query": item.query,
                        "weight": item.weight,
                    }
                    for item in plan.items
                ],
                "normalized_probabilities": plan.normalized_probabilities,
            },
        }

        print("Semantic Vision Contract:")
        print(json.dumps(output, indent=2, ensure_ascii=True))

        if len(plan.items) != 3:
            print("Stage 4J failed: expected three composition candidates.")
            return 2

        if abs(sum(plan.normalized_probabilities) - 100.0) > 0.001:
            print("Stage 4J failed: composition probabilities do not total 100.")
            return 3

        print("Stage 4J semantic vision contract acceptance passed.")
        print("A live vision model is not yet attached in this package.")
        return 0

    except (
        ReferenceImageError,
        SemanticPlanError,
        SemanticVisionError,
        OSError,
        ValueError,
        KeyError,
    ) as exc:
        print("Stage 4J error: " + str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
