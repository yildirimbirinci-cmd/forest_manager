from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "src" / "forest_manager" / "forest_control" / "service.py"
APP = ROOT / "src" / "forest_manager" / "devtools" / "legacy" / "forest_pack_curve_control_stage5d38.py"


def test_service_exposes_verified_read_only_curve_boundary():
    text = SERVICE.read_text(encoding="utf-8")
    assert "def curve_points(" in text
    assert '"point_api_supported": False' in text
    assert '"point_read_supported": False' in text
    assert '"point_write_supported": False' in text
    assert '"point_count_change_supported": False' in text
    assert "send_command(\"FOREST_CONTROL_CURVE" not in text


def test_app_does_not_claim_unverified_point_write_support():
    text = APP.read_text(encoding="utf-8")
    assert '"curve_metadata_read": True' in text
    assert '"curve_point_read": False' in text
    assert '"existing_point_write": False' in text
    assert '"controller_access": False' in text


def test_stage5d38_keeps_bridge_surface_unchanged():
    text = SERVICE.read_text(encoding="utf-8")
    assert 'send_command("FOREST_CONTROL_DISCOVER")' in text
    assert "CURVE_POINTS" not in text
    assert "SET_CURVE" not in text


def test_stage5d38_app_compiles():
    spec = importlib.util.spec_from_file_location("stage5d38_app", APP)
    assert spec is not None
    assert spec.loader is not None
