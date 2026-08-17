from __future__ import annotations

import json
from pathlib import Path

from forest_manager.max_bridge import runtime_bridge as rb


def main() -> int:
    checks: list[dict] = []
    try:
        ping = rb.ensure_current_bridge()
        data = ping.get("data") or {}
        checks.append({
            "name": "bridge_identity",
            "passed": (
                data.get("bridge_version") == rb.EXPECTED_BRIDGE_VERSION
                and data.get("bridge_build_id") == rb.EXPECTED_BRIDGE_BUILD_ID
            ),
            "detail": data,
        })

        canonical = rb._bridge_source_path()
        checks.append({
            "name": "canonical_source_identity",
            "passed": rb._source_identity(canonical) == (
                rb.EXPECTED_BRIDGE_VERSION,
                rb.EXPECTED_BRIDGE_BUILD_ID,
            ),
            "detail": {
                "path": str(canonical),
                "identity": rb._source_identity(canonical),
            },
        })

        staged = rb._staged_bridge_path()
        checks.append({
            "name": "staged_update_consumed",
            "passed": not staged.exists(),
            "detail": str(staged),
        })

        startup_details = []
        startup_ok = True
        canonical_text = str(canonical).replace("\\", "\\\\")
        for target in rb._startup_targets():
            exists = target.is_file()
            text = target.read_text(encoding="utf-8", errors="replace") if exists else ""
            references_canonical = canonical_text in text or str(canonical) in text
            disabled_copy = target.with_name(target.name + rb.DISABLED_STARTUP_SUFFIX)
            item_ok = exists and references_canonical and not disabled_copy.exists()
            startup_ok = startup_ok and item_ok
            startup_details.append({
                "path": str(target),
                "exists": exists,
                "references_canonical": references_canonical,
                "disabled_copy_exists": disabled_copy.exists(),
            })
        checks.append({
            "name": "startup_loader_reenabled",
            "passed": startup_ok and bool(startup_details),
            "detail": startup_details,
        })

        ok = all(item["passed"] for item in checks)
        print(json.dumps({"ok": ok, "checks": checks}, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "checks": checks,
            "error": type(exc).__name__ + ": " + str(exc),
        }, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
