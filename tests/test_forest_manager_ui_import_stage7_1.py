from __future__ import annotations


def test_ui_controller_imports_without_qt_dependency():
    from forest_manager.ui.controller import ForestManagerUIController
    assert ForestManagerUIController is not None


def test_ui_launcher_module_import_is_lazy_enough_for_headless_validation():
    import forest_manager.app.forest_manager_ui_stage7_1 as launcher
    assert callable(launcher.main)
