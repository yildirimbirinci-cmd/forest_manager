from forest_manager.devtools.acceptance.stage8_ai_scene_execution_acceptance import (
    _duplicate_source_names,
    _preserved_named_sources,
    _resolved_manifest,
)


def test_resolved_manifest_keeps_only_groups_with_resolved_source_names():
    manifest = {
        "primary_forest": "FM_Forest_001",
        "groups": [
            {"group_id": "resolved-a", "source_names": ["Allium hollandicum 'Purple Sensation'"]},
            {"group_id": "unresolved", "source_names": []},
            {"group_id": "resolved-b", "source_names": ["Allamanda"]},
        ],
    }

    result = _resolved_manifest(manifest)

    assert [item["group_id"] for item in result["groups"]] == ["resolved-a", "resolved-b"]
    assert len(manifest["groups"]) == 3


def test_preserved_named_sources_requires_allium_and_allamanda_before_and_after():
    before = ("Allium hollandicum 'Purple Sensation'", "Allamanda", "Rosa canina")
    after = ("Allium hollandicum 'Purple Sensation'", "Allamanda", "Rudbeckia 'Goldsturm'")

    assert _preserved_named_sources(before, after) == {"allium": True, "allamanda": True}


def test_duplicate_source_detection_is_case_insensitive():
    assert _duplicate_source_names(("Allamanda", "ALLAMANDA")) == ["Allamanda"]
    assert _duplicate_source_names(("Allamanda", "Allium")) == []
