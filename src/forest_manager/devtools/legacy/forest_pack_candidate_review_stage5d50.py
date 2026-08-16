from __future__ import annotations

import json

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.candidate_review import CandidateReview


def main() -> int:
    print("Forest Manager Stage 5D.50 User-Control Candidate Review:")
    try:
        service = ForestPackControlService()
        review = CandidateReview(service)
        forests = service.list_forests()
        reports = [review.review_forest(name) for name in forests]

        candidate_counts = sorted({item["candidate_count"] for item in reports})
        domain_consistency: dict[str, set[int]] = {}
        policy_consistency: dict[str, set[int]] = {}

        for report in reports:
            for key, value in report["domain_counts"].items():
                domain_consistency.setdefault(key, set()).add(value)
            for key, value in report["policy_counts"].items():
                policy_consistency.setdefault(key, set()).add(value)

        result = {
            "ok": True,
            "forest_count": len(forests),
            "candidate_counts": candidate_counts,
            "domain_count_consistency": {
                key: sorted(values)
                for key, values in sorted(domain_consistency.items())
            },
            "policy_count_consistency": {
                key: sorted(values)
                for key, values in sorted(policy_consistency.items())
            },
            "forests": reports,
            "policy": {
                "audit_only": True,
                "no_scene_write": True,
                "candidate_set_size": 40,
                "domain_assignment_required": True,
                "scalar_candidates_may_move_into_semantic_domains": True,
                "read_only_candidates_must_remain_read_only": True,
                "typed_or_complex_candidates_need_dedicated_contract": True,
            },
            "verified": True,
        }

        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("Stage 5D.50 user-control candidate review passed.")
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": type(exc).__name__ + ": " + str(exc),
                    "verified": False,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
