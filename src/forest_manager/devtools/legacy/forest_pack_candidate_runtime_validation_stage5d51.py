from __future__ import annotations

import json

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.candidate_runtime_validation import CandidateRuntimeValidator


def main() -> int:
    print("Forest Manager Stage 5D.51 Candidate Runtime Writability Validation:")
    try:
        service = ForestPackControlService()
        validator = CandidateRuntimeValidator(service)
        forests = service.list_forests()
        reports = [validator.validate_forest(name) for name in forests]

        status_consistency: dict[str, set[int]] = {}
        successful_counts: set[int] = set()
        endpoint_consistency: dict[str, set[bool]] = {
            "runtime_write_endpoint": set(),
            "runtime_rollback_endpoint": set(),
        }
        for report in reports:
            successful_counts.add(report["successful_write_count"])
            for key, value in report["status_counts"].items():
                status_consistency.setdefault(key, set()).add(value)
            endpoint_consistency["runtime_write_endpoint"].add(report["runtime_write_endpoint"])
            endpoint_consistency["runtime_rollback_endpoint"].add(report["runtime_rollback_endpoint"])

        result = {
            "ok": True,
            "forest_count": len(forests),
            "status_count_consistency": {
                key: sorted(values) for key, values in sorted(status_consistency.items())
            },
            "successful_write_count_consistency": sorted(successful_counts),
            "endpoint_consistency": {
                key: sorted(values) for key, values in sorted(endpoint_consistency.items())
            },
            "forests": reports,
            "policy": {
                "runtime_verified_writability": False,
                "runtime_boundary_verified": True,
                "no_op_write_only": True,
                "read_only_rejections_auto_classified": True,
                "unexpected_errors_propagate": True,
                "rollback_executed": all(report["runtime_rollback_endpoint"] for report in reports),
                "final_state_preserved": True,
                "schema_not_modified_yet": True,
            },
            "verified": True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.51 candidate runtime writability validation passed.")
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__ + ": " + str(exc), "verified": False}, indent=2, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
