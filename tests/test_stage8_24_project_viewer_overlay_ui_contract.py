from pathlib import Path


def test_project_viewer_exposes_source_switch_and_semantic_overlay_controls():
    source = (Path(__file__).parents[1] / "src" / "forest_manager" / "ui" / "project_viewer.py").read_text(encoding="utf-8")
    assert 'QLabel("Source")' in source
    assert 'QCheckBox("AI")' in source
    assert 'QCheckBox("Artist Confirmed")' in source
    assert 'QCheckBox("Artist Override")' in source
    assert 'QCheckBox("Role Labels")' in source
    assert "set_active_source" in source
    assert "set_annotation_source_visible" in source
    assert "QGraphicsSimpleTextItem" in source
