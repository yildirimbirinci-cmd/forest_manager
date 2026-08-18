from pathlib import Path
import inspect
from forest_manager.max_bridge import runtime_bridge
from forest_manager.ui.controller import ForestManagerUIController, ForestUIState


def test_runtime_bridge_exposes_read_only_segment_selection_contract():
    src = inspect.getsource(runtime_bridge.read_selected_spline_segments)
    assert "GET_SELECTION_SPLINE_SEGMENTS" in src
    assert "read-only" in src.lower()


def test_controller_persists_wall_edge_through_scene_state_gateway():
    src = inspect.getsource(ForestManagerUIController.mark_selected_segments_as_wall)
    assert "snapshot_and_working_copy" in src
    assert "write_verified" in src
    assert "read_manifest" in src
    assert "restore_snapshot" in src


def test_ui_state_exposes_wall_edge_summary():
    assert ForestUIState().wall_edge_summary == "No Wall Edge annotation"


def test_bridge_has_wall_edge_read_command_and_updated_identity():
    bridge = Path(__file__).resolve().parents[1] / "maxscripts" / "ForestManager_Bridge.ms"
    text = bridge.read_text(encoding="utf-8-sig")
    assert '\\"bridge_version\\":\\"0.9.83\\"' in text
    assert 'stage8-wall-edge-annotation-20260818a' in text
    assert 'GET_SELECTION_SPLINE_SEGMENTS' in text
    assert 'getSegSelection node 1' in text
