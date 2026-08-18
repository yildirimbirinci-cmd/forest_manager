from __future__ import annotations

import forest_manager.forest_control.ai_t2_scene_region_runtime as module


def test_recursive_group_extraction_finds_nested_runtime_groups():
    payload = {
        "ok": True,
        "detail": {
            "manifest": {
                "groups": [
                    {
                        "group_id": "plant_group:1:foreground_mass",
                        "source_names": ["Lavender"],
                    }
                ]
            }
        },
    }
    groups = module._find_group_list(payload)
    assert groups
    assert groups[0]["group_id"] == "plant_group:1:foreground_mass"


def test_normalization_derives_semantic_role_from_group_id():
    groups = module.normalize_runtime_groups(
        [
            {
                "group_id": "plant_group:1:foreground_mass",
                "source_names": ["Lavender"],
            }
        ]
    )
    assert groups[0]["semantic_role"] == "foreground_mass"
    assert groups[0]["source_names"] == ["Lavender"]


def test_runtime_prefers_acceptance_payload_groups(monkeypatch):
    monkeypatch.setattr(
        module,
        "run_ai_t2_resolution_acceptance",
        lambda reference_image, python_executable=None: {
            "ok": True,
            "resolved_group_count": 1,
            "groups": [
                {
                    "group_id": "plant_group:1:foreground_mass",
                    "source_names": ["Lavender"],
                }
            ],
        },
    )
    monkeypatch.setattr(
        module,
        "read_plant_group_manifest",
        lambda: (_ for _ in ()).throw(AssertionError("manifest fallback should not run")),
    )

    payload, groups, source = module.resolve_ai_t2_runtime_groups("ignored.png")
    assert payload["ok"] is True
    assert len(groups) == 1
    assert source == "ai_t2_acceptance_payload"


def test_runtime_falls_back_to_verified_live_manifest(monkeypatch):
    monkeypatch.setattr(
        module,
        "run_ai_t2_resolution_acceptance",
        lambda reference_image, python_executable=None: {
            "ok": True,
            "resolved_group_count": 1,
        },
    )
    monkeypatch.setattr(
        module,
        "read_plant_group_manifest",
        lambda: {
            "groups": [
                {
                    "group_id": "plant_group:1:foreground_mass",
                    "source_names": ["Lavender"],
                }
            ]
        },
    )

    _payload, groups, source = module.resolve_ai_t2_runtime_groups("ignored.png")
    assert len(groups) == 1
    assert source == "verified_live_plant_group_manifest_fallback"
