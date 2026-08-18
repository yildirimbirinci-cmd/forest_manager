from pathlib import Path


def test_bridge_uses_diversity_slot_without_rewriting_distribution_units():
    text = Path("maxscripts/ForestManager_Bridge.ms").read_text(encoding="utf-8")
    start = text.index("fn plantGroupBindSingleForestDiversityMapJson")
    end = text.index("\n    fn ", start + 10)
    body = text[start:end]
    assert "forestNode.divtmap = bitmapMap" in body
    assert "forestNode.divers = 1" in body
    assert "forestNode.units_x = mapWidth" not in body
    assert "forestNode.units_y = mapHeight" not in body
    assert "Diversity-map binding changed units_x" in body
    assert "Diversity-map binding changed units_y" in body
    assert "density_preserved" in body


def test_runtime_bridge_targets_0982_staged_bridge():
    text = Path("src/forest_manager/max_bridge/runtime_bridge.py").read_text(encoding="utf-8")
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.82"' in text
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage8-diversity-slot-density-preserve-20260818a"' in text
    assert 'STAGED_BRIDGE_FILENAME = "ForestManager_Bridge_0_9_82.ms"' in text
    assert Path("maxscripts/ForestManager_Bridge_0_9_82.ms").is_file()


def test_local_and_staged_bridge_identity_matches_runtime_expectation():
    runtime = Path("src/forest_manager/max_bridge/runtime_bridge.py").read_text(encoding="utf-8")
    for bridge_path in (
        Path("maxscripts/ForestManager_Bridge.ms"),
        Path("maxscripts/ForestManager_Bridge_0_9_82.ms"),
    ):
        text = bridge_path.read_text(encoding="utf-8-sig")
        assert r'\"bridge_version\":\"0.9.82\"' in text
        assert r'\"bridge_build_id\":\"stage8-diversity-slot-density-preserve-20260818a\"' in text
    assert Path("maxscripts/ForestManager_Bridge.ms").read_bytes() == Path("maxscripts/ForestManager_Bridge_0_9_82.ms").read_bytes()
    assert 'EXPECTED_BRIDGE_VERSION = "0.9.82"' in runtime
    assert 'EXPECTED_BRIDGE_BUILD_ID = "stage8-diversity-slot-density-preserve-20260818a"' in runtime
