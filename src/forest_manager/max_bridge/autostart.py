from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import tempfile


BRIDGE_FILENAME = "ForestManager_Bridge.ms"
AUTOSTART_FILENAME = "ForestManager_AutoStart.ms"


class BridgeAutoStartError(RuntimeError):
    pass


@dataclass(frozen=True)
class BridgeAutoStartInstall:
    max_user_dir: Path
    startup_dir: Path
    bridge_path: Path
    autostart_path: Path
    verified: bool

    def to_dict(self) -> dict:
        return {
            "max_user_dir": str(self.max_user_dir),
            "startup_dir": str(self.startup_dir),
            "bridge_path": str(self.bridge_path),
            "autostart_path": str(self.autostart_path),
            "verified": bool(self.verified),
        }


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def source_bridge_path(root: Path | None = None) -> Path:
    base = Path(root) if root is not None else project_root()
    path = base / "maxscripts" / BRIDGE_FILENAME
    if not path.is_file():
        raise BridgeAutoStartError(f"Forest Manager bridge source was not found: {path}")
    return path


def source_autostart_path(root: Path | None = None) -> Path:
    base = Path(root) if root is not None else project_root()
    path = base / "maxscripts" / AUTOSTART_FILENAME
    if not path.is_file():
        raise BridgeAutoStartError(f"Forest Manager autostart source was not found: {path}")
    return path


def _year_from_dir_name(name: str) -> int | None:
    head = str(name or "").strip().split(" ", 1)[0]
    try:
        value = int(head)
    except ValueError:
        return None
    return value if 2000 <= value <= 2200 else None


def discover_3dsmax_user_dirs(
    *,
    local_app_data: Path | str | None = None,
    year: int | None = None,
) -> list[Path]:
    base = Path(
        local_app_data
        if local_app_data is not None
        else os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    )
    max_root = base / "Autodesk" / "3dsMax"
    if not max_root.is_dir():
        return []

    matches: list[tuple[int, Path]] = []
    for version_dir in max_root.iterdir():
        if not version_dir.is_dir():
            continue
        detected_year = _year_from_dir_name(version_dir.name)
        if detected_year is None:
            continue
        if year is not None and detected_year != int(year):
            continue

        for locale_dir in version_dir.iterdir():
            if not locale_dir.is_dir():
                continue
            scripts_dir = locale_dir / "scripts"
            if scripts_dir.is_dir() or locale_dir.name.upper() in {"ENU", "EN-US"}:
                matches.append((detected_year, locale_dir))

    matches.sort(key=lambda row: (row[0], str(row[1]).casefold()))
    return [path for _, path in matches]


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=destination.name + ".",
        suffix=".tmp",
        dir=str(destination.parent),
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        shutil.copy2(source, temp_path)
        temp_path.replace(destination)
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass


def _same_bytes(left: Path, right: Path) -> bool:
    return left.is_file() and right.is_file() and left.read_bytes() == right.read_bytes()


def install_bridge_autostart(
    max_user_dir: Path | str,
    *,
    root: Path | None = None,
) -> BridgeAutoStartInstall:
    max_dir = Path(max_user_dir).resolve()
    bridge_source = source_bridge_path(root)
    autostart_source = source_autostart_path(root)

    startup_dir = max_dir / "scripts" / "startup"
    bridge_target = startup_dir / BRIDGE_FILENAME
    autostart_target = startup_dir / AUTOSTART_FILENAME

    _atomic_copy(bridge_source, bridge_target)
    _atomic_copy(autostart_source, autostart_target)

    verified = _same_bytes(bridge_source, bridge_target) and _same_bytes(
        autostart_source, autostart_target
    )
    if not verified:
        raise BridgeAutoStartError(
            f"Forest Manager bridge autostart verification failed: {startup_dir}"
        )

    return BridgeAutoStartInstall(
        max_user_dir=max_dir,
        startup_dir=startup_dir,
        bridge_path=bridge_target,
        autostart_path=autostart_target,
        verified=True,
    )


def install_detected_bridge_autostart(
    *,
    year: int | None = None,
    local_app_data: Path | str | None = None,
    root: Path | None = None,
) -> list[BridgeAutoStartInstall]:
    max_dirs = discover_3dsmax_user_dirs(local_app_data=local_app_data, year=year)
    if not max_dirs:
        suffix = f" for 3ds Max {year}" if year is not None else ""
        raise BridgeAutoStartError(f"No 3ds Max user profile was found{suffix}.")
    return [install_bridge_autostart(path, root=root) for path in max_dirs]
