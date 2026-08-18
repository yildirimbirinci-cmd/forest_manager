from __future__ import annotations

import json
from pathlib import Path

from forest_manager.site_model.local_vision_provider import LocalVisionProvider, LocalVisionProviderError


def _response(groups):
    return {"choices": [{"message": {"content": json.dumps({"groups": groups})}}]}


def _image(tmp_path: Path) -> Path:
    path = tmp_path / "ref.png"
    path.write_bytes(b"not-a-real-image-but-provider-only-base64-encodes-it")
    return path


def test_analyze_runs_single_refinement_pass_and_returns_refined_groups(tmp_path):
    calls = []
    first = [
        {
            "label": "ground layer",
            "semantic_role": "groundcover",
            "coverage_weight": 0.5,
            "naturalness": "Balanced",
            "cluster_character": "Large Masses",
            "confidence": 0.8,
            "species_candidates": [],
        },
        {
            "label": "rear shrub",
            "semantic_role": "structural_shrub",
            "coverage_weight": 0.5,
            "naturalness": "Balanced",
            "cluster_character": "Medium Clusters",
            "confidence": 0.8,
            "species_candidates": [{"name": "Japanese maple", "confidence": 0.7}],
        },
    ]
    refined = [
        {
            "label": "ground layer",
            "semantic_role": "groundcover",
            "coverage_weight": 0.5,
            "naturalness": "Balanced",
            "cluster_character": "Large Masses",
            "confidence": 0.8,
            "species_candidates": [
                {"name": "creeping thyme", "confidence": 0.6},
                {"name": "Ajuga reptans", "confidence": 0.5},
            ],
        },
        {
            "label": "rear shrub",
            "semantic_role": "structural_shrub",
            "coverage_weight": 0.5,
            "naturalness": "Balanced",
            "cluster_character": "Medium Clusters",
            "confidence": 0.8,
            "species_candidates": [
                {"name": "Berberis", "confidence": 0.6},
                {"name": "Rosa canina", "confidence": 0.5},
            ],
        },
    ]

    def transport(endpoint, body, timeout):
        calls.append(json.loads(body.decode("utf-8")))
        return _response(first if len(calls) == 1 else refined)

    result = LocalVisionProvider(transport=transport).analyze(str(_image(tmp_path)))

    assert len(calls) == 2
    assert calls[0]["temperature"] == 0.1
    assert calls[1]["temperature"] == 0.05
    refinement_text = calls[1]["messages"][0]["content"][0]["text"]
    assert "Audit and refine" in refinement_text
    assert "Growth form must agree with semantic_role" in refinement_text
    assert result.groups[0]["source_names"] == ["creeping thyme", "Ajuga reptans"]
    assert result.groups[1]["source_names"] == ["Berberis", "Rosa canina"]


def test_refinement_preserves_unresolved_group_for_downstream_exclusion(tmp_path):
    groups = [
        {
            "label": "ground layer",
            "semantic_role": "groundcover",
            "coverage_weight": 1.0,
            "naturalness": "Balanced",
            "cluster_character": "Large Masses",
            "confidence": 0.8,
            "species_candidates": [],
        }
    ]

    provider = LocalVisionProvider(transport=lambda endpoint, body, timeout: _response(groups))
    result = provider.analyze(str(_image(tmp_path)))

    assert len(result.groups) == 1
    assert result.groups[0]["semantic_role"] == "groundcover"
    assert result.groups[0]["source_names"] == []
    assert provider._audit_refined_groups(result.groups) == ("ground layer",)


def test_prompt_requires_candidates_and_growth_form_consistency():
    prompt = LocalVisionProvider._prompt()
    assert "must include 1 to 3 non-empty species_candidates" in prompt
    assert "Keep growth form consistent with semantic_role" in prompt
