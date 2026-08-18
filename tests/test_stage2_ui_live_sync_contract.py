from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "src" / "forest_manager" / "ui" / "main_window.py"
CONTROLLER = ROOT / "src" / "forest_manager" / "ui" / "controller.py"


def test_plant_group_live_sync_is_debounced_and_uses_verified_controller_endpoints():
    main = MAIN.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")

    assert "from PySide6.QtCore import Qt, QTimer" in main
    assert "self._live_sync_delay_ms = 75" in main
    assert 'self.group_scale.valueChanged.connect(lambda value: self._schedule_plant_group_live("scale", value))' in main
    assert 'self.group_probability.valueChanged.connect(lambda value: self._schedule_plant_group_live("probability", value))' in main
    assert "timer.setSingleShot(True)" in main
    assert "timer.start(self._live_sync_delay_ms)" in main
    assert "self.controller.set_selected_group_scale(value)" in main
    assert "self.controller.set_selected_group_probability(value)" in main

    # Existing generic Advanced property workflow must remain staged/pending.
    assert "state = self.controller.set_pending_value(property_name, value)" in main
    assert "def set_pending_value(self, property_name: str, value: Any)" in controller


def test_visibility_keeps_immediate_verified_live_write():
    main = MAIN.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")

    assert "self.group_enabled.toggled.connect(self._group_enabled_changed)" in main
    assert "self.controller.set_selected_group_enabled(bool(enabled))" in main
    assert 'return self._apply_group_runtime_live(group, "enabled", bool(enabled))' in controller
