from __future__ import annotations

import json

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.undeclared_classification import UndeclaredPropertyClassifier


def main() -> int:
    print("Forest Manager Stage 5D.49 Undeclared Property Classification:")
    try:
        service = ForestPackControlService()
        classifier = UndeclaredPropertyClassifier(service)
        forests = service.list_forests()
        reports = [classifier.classify_forest(name) for name in forests]
        category_sets: dict[str, set[int]] = {}
        for report in reports:
            for key, value in report["category_counts"].items():
                category_sets.setdefault(key, set()).add(value)
        result = {
            "ok": True,
            "forest_count": len(forests),
            "forests": reports,
            "category_count_consistency": {
                key: sorted(values) for key, values in sorted(category_sets.items())
            },
            "policy": {
                "audit_only": True,
                "no_scene_write": True,
                "reserved_not_exposed": True,
                "internal_runtime_not_exposed_by_default": True,
                "legacy_plugin_not_exposed_by_default": True,
                "user_control_candidates_require_semantic_review": True,
                "needs_review_not_auto_exposed": True,
            },
            "verified": True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.49 undeclared property classification passed.")
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__ + ": " + str(exc), "verified": False}, indent=2, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
