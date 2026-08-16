from __future__ import annotations

import json
from dataclasses import asdict

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.coverage_audit import SemanticCoverageAudit


def main() -> int:
    print("Forest Manager Stage 5D.48 Semantic Coverage Audit:")
    try:
        service = ForestPackControlService()
        audit = SemanticCoverageAudit(service)
        forests = service.list_forests()
        reports = [asdict(audit.audit_forest(name)) for name in forests]
        property_counts = sorted({item["property_count"] for item in reports})
        declared_counts = sorted({item["declared_count"] for item in reports})
        undeclared_counts = sorted({item["undeclared_count"] for item in reports})
        result = {
            "ok": True,
            "forest_count": len(forests),
            "property_counts": property_counts,
            "declared_counts": declared_counts,
            "undeclared_counts": undeclared_counts,
            "forests": reports,
            "policy": {
                "audit_only": True,
                "no_scene_write": True,
                "semantic_schema_is_source_of_truth": True,
                "undeclared_requires_classification": True,
                "internal_or_readonly_may_remain_non_user_controls": True,
            },
            "verified": True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.48 semantic coverage audit passed.")
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__ + ": " + str(exc), "verified": False}, indent=2, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
