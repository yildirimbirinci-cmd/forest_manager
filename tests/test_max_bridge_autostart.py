from pathlib import Path

from forest_manager.max_bridge.autostart import (
    AUTOSTART_FILENAME,
    BRIDGE_FILENAME,
    discover_3dsmax_user_dirs,
    install_bridge_autostart,
)


def _make_project(root: Path) -> None:
    scripts = root / "maxscripts"
    scripts.mkdir(parents=True)
    (scripts / BRIDGE_FILENAME).write_text("bridge-current\n", encoding="utf-8")
    (scripts / AUTOSTART_FILENAME).write_text("autostart-current\n", encoding="utf-8")


def test_discover_3dsmax_user_dir_by_year(tmp_path):
    local = tmp_path / "Local"
    enu = local / "Autodesk" / "3dsMax" / "2020 - 64bit" / "ENU"
    (enu / "scripts").mkdir(parents=True)
    other = local / "Autodesk" / "3dsMax" / "2024 - 64bit" / "ENU"
    (other / "scripts").mkdir(parents=True)

    assert discover_3dsmax_user_dirs(local_app_data=local, year=2020) == [enu]


def test_install_copies_current_bridge_and_startup_shim(tmp_path):
    root = tmp_path / "project"
    _make_project(root)
    max_user = tmp_path / "2020 - 64bit" / "ENU"

    result = install_bridge_autostart(max_user, root=root)

    assert result.verified is True
    assert result.bridge_path.read_text(encoding="utf-8") == "bridge-current\n"
    assert result.autostart_path.read_text(encoding="utf-8") == "autostart-current\n"
    assert result.startup_dir == max_user.resolve() / "scripts" / "startup"


def test_reinstall_replaces_stale_bridge_idempotently(tmp_path):
    root = tmp_path / "project"
    _make_project(root)
    max_user = tmp_path / "2020 - 64bit" / "ENU"
    startup = max_user / "scripts" / "startup"
    startup.mkdir(parents=True)
    (startup / BRIDGE_FILENAME).write_text("old-bridge\n", encoding="utf-8")
    (startup / AUTOSTART_FILENAME).write_text("old-shim\n", encoding="utf-8")

    first = install_bridge_autostart(max_user, root=root)
    second = install_bridge_autostart(max_user, root=root)

    assert first.verified and second.verified
    assert (startup / BRIDGE_FILENAME).read_text(encoding="utf-8") == "bridge-current\n"
    assert (startup / AUTOSTART_FILENAME).read_text(encoding="utf-8") == "autostart-current\n"
