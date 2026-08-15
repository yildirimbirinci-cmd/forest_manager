from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class T2AssetRecord:
    id: int
    name: str
    file_path: Path
    folder_path: Path
    extension: str
    category: str
    missing: bool
    source: str = "database"

    @property
    def exists(self) -> bool:
        return self.file_path.is_file()


class T2AssetCatalogError(RuntimeError):
    pass


class T2AssetCatalog:
    """Read-only access to T2's database with T2-library filesystem fallback."""

    def __init__(self, db_path: Path | str | None = None, settings_path: Path | str | None = None):
        local_app_data = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        self.db_path = Path(db_path) if db_path is not None else local_app_data / "T2Manager" / "Database" / "assets.db"
        self.settings_path = Path(settings_path) if settings_path is not None else local_app_data / "T2Manager" / "Config" / "settings.json"

    def _connect_read_only(self) -> sqlite3.Connection:
        if not self.db_path.is_file():
            raise T2AssetCatalogError(f"T2 asset database was not found: {self.db_path}")
        try:
            return sqlite3.connect(self.db_path.resolve().as_uri() + "?mode=ro", uri=True)
        except sqlite3.Error as exc:
            raise T2AssetCatalogError(f"Could not open T2 asset database read-only: {exc}") from exc

    @staticmethod
    def _record(row: tuple) -> T2AssetRecord:
        return T2AssetRecord(
            id=int(row[0]), name=str(row[1] or ""), file_path=Path(str(row[2] or "")),
            folder_path=Path(str(row[3] or "")), extension=str(row[4] or "").lower(),
            category=str(row[5] or ""), missing=bool(row[6]), source="database",
        )

    def _database_search(self, text: str, limit: int) -> list[T2AssetRecord]:
        if not self.db_path.is_file():
            return []
        sql = """
            SELECT id, name, file_path, folder_path, extension, category, COALESCE(missing, 0)
            FROM assets
            WHERE lower(extension) = '.max' AND COALESCE(missing, 0) = 0
        """
        params: list[object] = []
        if text:
            sql += " AND (name LIKE ? OR category LIKE ? OR folder_path LIKE ?)"
            like = f"%{text}%"; params.extend([like, like, like])
        sql += " ORDER BY name COLLATE NOCASE LIMIT ?"; params.append(limit)
        try:
            with self._connect_read_only() as conn:
                rows = conn.execute(sql, tuple(params)).fetchall()
        except sqlite3.Error as exc:
            raise T2AssetCatalogError(f"T2 asset query failed: {exc}") from exc
        return [self._record(row) for row in rows]

    def _load_settings(self) -> dict:
        if not self.settings_path.is_file():
            return {}
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            raise T2AssetCatalogError(f"Could not read T2 settings: {exc}") from exc

    def library_roots(self) -> list[Path]:
        data = self._load_settings()
        raw: list[str] = []
        for key in ("library_path", "local_sync_path", "project_library_path"):
            value = str(data.get(key) or "").strip()
            if value:
                raw.append(value)
        for item in data.get("external_libraries", []) or []:
            if isinstance(item, str):
                raw.append(item)
            elif isinstance(item, dict):
                value = str(item.get("path") or item.get("library_path") or "").strip()
                if value:
                    raw.append(value)
        roots: list[Path] = []
        seen: set[str] = set()
        for value in raw:
            path = Path(value)
            key = str(path).casefold()
            if key in seen or not path.is_dir():
                continue
            seen.add(key); roots.append(path)
        return roots

    def _filesystem_search(self, text: str, limit: int) -> list[T2AssetRecord]:
        query = text.casefold()
        records: list[T2AssetRecord] = []
        seen: set[str] = set()
        for root in self.library_roots():
            try:
                iterator = root.rglob("*.max")
                for path in iterator:
                    if not path.is_file():
                        continue
                    full = str(path)
                    key = full.casefold()
                    if key in seen:
                        continue
                    category = path.parent.name
                    if query and query not in path.stem.casefold() and query not in category.casefold() and query not in full.casefold():
                        continue
                    seen.add(key)
                    records.append(T2AssetRecord(
                        id=0, name=path.stem, file_path=path, folder_path=path.parent,
                        extension=".max", category=category, missing=False, source="library_scan",
                    ))
                    if len(records) >= limit:
                        return sorted(records, key=lambda r: r.name.casefold())
            except OSError:
                continue
        return sorted(records, key=lambda r: r.name.casefold())[:limit]

    def search_max_assets(self, text: str = "", *, limit: int = 50, require_existing_file: bool = True) -> list[T2AssetRecord]:
        query = str(text or "").strip()
        safe_limit = max(1, min(int(limit), 500))
        records = self._database_search(query, safe_limit)
        if require_existing_file:
            records = [record for record in records if record.exists]
        if records:
            return records
        return self._filesystem_search(query, safe_limit)

    def diagnostics(self) -> dict:
        result = {
            "database": str(self.db_path), "database_exists": self.db_path.is_file(),
            "settings": str(self.settings_path), "settings_exists": self.settings_path.is_file(),
            "library_roots": [str(p) for p in self.library_roots()],
            "database_total_rows": 0, "database_max_rows": 0,
        }
        if self.db_path.is_file():
            try:
                with self._connect_read_only() as conn:
                    result["database_total_rows"] = int(conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0])
                    result["database_max_rows"] = int(conn.execute("SELECT COUNT(*) FROM assets WHERE lower(extension)='.max'").fetchone()[0])
            except Exception as exc:
                result["database_error"] = str(exc)
        return result
