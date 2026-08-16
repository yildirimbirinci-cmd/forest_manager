from pathlib import Path


def test_main_window_integrates_project_viewer_without_replacing_artist_controls():
    source = (Path(__file__).parents[1] / "src" / "forest_manager" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert 'addTab(self._create_artist_controls_page(), "Artist Controls")' in source
    assert 'addTab(self.project_viewer, "Project Viewer")' in source
    assert "ProjectViewerWidget(self.site_viewer_presenter)" in source
    assert "def refresh_project_viewer" in source


def test_project_viewer_exposes_click_selection_and_artist_correction_actions():
    source = (Path(__file__).parents[1] / "src" / "forest_manager" / "ui" / "project_viewer.py").read_text(encoding="utf-8")
    assert "mousePressEvent" in source
    assert "Approve AI Role" in source
    assert "Assign Role" in source
    assert "Reject" in source
    assert "AnnotationSource.AI_INFERRED" in source
    assert "AnnotationSource.ARTIST_OVERRIDE" in source
