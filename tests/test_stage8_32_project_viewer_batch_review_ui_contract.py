from pathlib import Path


def test_project_viewer_exposes_confidence_review_and_batch_selection_controls():
    text = Path(__file__).parents[1].joinpath("src/forest_manager/ui/project_viewer.py").read_text(encoding="utf-8")
    assert 'QCheckBox("Low Confidence Review")' in text
    assert 'QPushButton("Select Visible")' in text
    assert "set_low_confidence_review" in text
    assert "selection_mixed_roles" in text
