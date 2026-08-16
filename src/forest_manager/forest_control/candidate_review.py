from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .service import ForestPackControlService
from .undeclared_classification import USER_CONTROL_CANDIDATES


CANDIDATE_DOMAIN_MAP: dict[str, str] = {
    "camdensact": "camera",
    "camdensear": "camera",
    "camdensfar": "camera",
    "camscaact": "camera",
    "distmode": "distribution",
    "divers": "distribution",
    "divmapchan": "distribution",
    "divmapnoise": "distribution",
    "divtmap": "distribution",
    "drotation": "distribution",
    "maxdensity": "distribution",
    "randstacked": "distribution",
    "seed": "distribution",
    "seedtype": "distribution",
    "threshold": "distribution",
    "sepsubsplines": "distribution",
    "spdensact": "surface",
    "spdensexc": "surface",
    "spdensinc": "surface",
    "spscalact": "surface",
    "spscalexc": "surface",
    "spscalinc": "surface",
    "spscalz": "surface",
    "scalelope": "surface",
    "offset_X": "transform",
    "offset_Y": "transform",
    "mirror": "transform",
    "sdgizmo": "transform",
    "iconSize": "display",
    "hidecustom": "display",
    "fastopac": "display",
    "collpreview": "display",
    "radius": "display",
    "opaclevel": "render",
    "renderid": "render",
    "pf_efonlyrender": "render",
    "ssitself": "render",
    "collheight": "collision",
    "mode": "collision",
    "geomtex": "material",
}


@dataclass(frozen=True)
class CandidateReviewItem:
    name: str
    domain: str
    value: Any
    value_class: str | None
    write_mode: str | None
    writable: bool | None
    recommended_policy: str


class CandidateReview:
    def __init__(self, service: ForestPackControlService | None = None) -> None:
        self.service = service or ForestPackControlService()

    def _inventory_map(self, forest_name: str) -> dict[str, dict[str, Any]]:
        payload = self.service.inventory(forest_name)
        rows = (
            payload.get("properties")
            or payload.get("inventory")
            or payload.get("items")
            or []
        )
        if isinstance(rows, dict):
            rows = rows.values()
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = row.get("name") or row.get("property_name")
            if name:
                result[str(name)] = row
        return result

    def review_forest(self, forest_name: str) -> dict[str, Any]:
        inventory = self._inventory_map(forest_name)
        items: list[CandidateReviewItem] = []

        for name in sorted(USER_CONTROL_CANDIDATES):
            metadata = inventory.get(name, {})

            value_class = metadata.get("value_class")
            write_mode = metadata.get("write_mode") or metadata.get("mode")
            writable = metadata.get("writable")
            domain = CANDIDATE_DOMAIN_MAP.get(name, "needs_domain_review")

            if write_mode == "scalar":
                recommended_policy = "semantic_scalar_candidate"
            elif write_mode == "color":
                recommended_policy = "typed_color_candidate"
            elif write_mode == "read_only":
                recommended_policy = "semantic_read_only_candidate"
            else:
                recommended_policy = "needs_write_contract_review"

            items.append(
                CandidateReviewItem(
                    name=name,
                    domain=domain,
                    value=metadata.get("value"),
                    value_class=value_class,
                    write_mode=write_mode,
                    writable=writable,
                    recommended_policy=recommended_policy,
                )
            )

        domain_counts: dict[str, int] = {}
        policy_counts: dict[str, int] = {}
        for item in items:
            domain_counts[item.domain] = domain_counts.get(item.domain, 0) + 1
            policy_counts[item.recommended_policy] = (
                policy_counts.get(item.recommended_policy, 0) + 1
            )

        return {
            "forest_name": forest_name,
            "candidate_count": len(items),
            "domain_counts": dict(sorted(domain_counts.items())),
            "policy_counts": dict(sorted(policy_counts.items())),
            "candidates": [
                {
                    "name": item.name,
                    "domain": item.domain,
                    "value": item.value,
                    "value_class": item.value_class,
                    "write_mode": item.write_mode,
                    "writable": item.writable,
                    "recommended_policy": item.recommended_policy,
                }
                for item in items
            ],
        }
