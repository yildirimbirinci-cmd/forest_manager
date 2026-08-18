from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from forest_manager.site_model.local_vision_provider import LocalVisionProvider
from forest_manager.site_model.reference_image import ReferenceImageAnalyzer


def _transport(_endpoint: str, body: bytes, _timeout: float) -> dict:
    request_payload = json.loads(body.decode("utf-8"))
    assert request_payload["model"] == "Qwen3-VL-4B-Instruct-Q4_K_M"
    assert request_payload["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    content = {
        "groups": [
            {
                "label": "Flower Accent",
                "semantic_role": "flower_accent",
                "coverage_weight": 7,
                "naturalness": "Natural",
                "cluster_character": "Small Groups",
                "confidence": 0.9,
                "species_candidates": [
                    {"name": "Rudbeckia", "confidence": 0.8},
                    {"name": "Aster", "confidence": 0.6},
                ],
            },
            {
                "label": "Structural Shrub",
                "semantic_role": "structural_shrub",
                "coverage_weight": 3,
                "naturalness": "Ordered",
                "cluster_character": "Large Masses",
                "confidence": 0.85,
                "species_candidates": [{"name": "Rosa", "confidence": 0.75}],
            },
        ]
    }
    return {"choices": [{"message": {"content": json.dumps(content)}}]}


def test_local_vision_provider_converts_variable_groups_to_reference_analysis(tmp_path: Path):
    image = tmp_path / "ref.png"
    Image.new("RGB", (32, 24)).save(image)
    provider = LocalVisionProvider(transport=_transport)
    analysis = ReferenceImageAnalyzer().analyze_with_provider(str(image), provider)
    assert analysis.analysis_provider == "forest_manager_local"
    assert analysis.analysis_model == "Qwen3-VL-4B-Instruct-Q4_K_M"
    assert analysis.analysis_version == "stage8-reference-image-variable-groups-v2"
    assert len(analysis.zones) == 2
    assert abs(analysis.coverage_total - 1.0) < 1e-9
    assert analysis.zones[0].source_names == ("Rudbeckia", "Aster")
    assert analysis.zones[1].source_names == ("Rosa",)
    assert analysis.zones[0].mask_path is None
