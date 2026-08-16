from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .schema import SiteModelSnapshot


class SiteModelPersistence:
    """Atomic JSON persistence for Stage 8 site geometry and semantic corrections."""

    def save(self, path: str | os.PathLike[str], snapshot: SiteModelSnapshot) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(snapshot.to_dict(), handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, target)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
        return target

    def load(self, path: str | os.PathLike[str]) -> SiteModelSnapshot:
        target = Path(path)
        with target.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("site model persistence payload must be a JSON object")
        return SiteModelSnapshot.from_dict(payload)
