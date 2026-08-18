from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from forest_manager.site_model import PlantingGroupIntent, PlantingPlan

from .stage8_asset_resolution import Stage8AssetResolutionError, Stage8T2AssetResolver


@dataclass(frozen=True)
class AIPlantGroupResolution:
    resolved_plan: PlantingPlan
    evidence: tuple[dict[str, Any], ...]
    excluded_groups: tuple[dict[str, Any], ...]


class AIPlantGroupAssetResolver:
    """Resolve AI visual species hypotheses against real T2 assets.

    AI source names are hypotheses, not scene sources. For each visual Plant
    Group the candidates are tried in confidence order and only the first real
    T2 asset match is promoted. Groups with no usable T2 match are excluded
    from the executable plan instead of inventing a source or failing the whole
    reference-image analysis.
    """

    def __init__(self, resolver: Stage8T2AssetResolver | None = None) -> None:
        self.resolver = resolver or Stage8T2AssetResolver()

    def resolve(self, plan: PlantingPlan) -> AIPlantGroupResolution:
        resolved_groups: list[PlantingGroupIntent] = []
        evidence: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []

        for group in plan.groups:
            candidates = tuple(str(value).strip() for value in group.source_names if str(value).strip())
            if not candidates:
                excluded.append({
                    "group_id": group.group_id,
                    "label": group.label,
                    "semantic_role": group.semantic_role,
                    "reason": "no_species_candidates",
                    "candidates": [],
                })
                continue

            failures: list[dict[str, str]] = []
            selected = None
            selected_requested = ""
            for requested_name in candidates:
                try:
                    record = self.resolver.resolve_asset_strict(requested_name, group.semantic_role)
                except Stage8AssetResolutionError as exc:
                    failures.append({"requested_name": requested_name, "error": str(exc)})
                    continue
                selected = record
                selected_requested = requested_name
                break

            if selected is None:
                excluded.append({
                    "group_id": group.group_id,
                    "label": group.label,
                    "semantic_role": group.semantic_role,
                    "reason": "no_t2_asset_match",
                    "candidates": list(candidates),
                    "failures": failures,
                })
                continue

            resolved_name = str(selected.name or "").strip()
            if not resolved_name:
                excluded.append({
                    "group_id": group.group_id,
                    "label": group.label,
                    "semantic_role": group.semantic_role,
                    "reason": "empty_t2_asset_name",
                    "candidates": list(candidates),
                })
                continue

            resolved_groups.append(replace(group, source_names=(resolved_name,)))
            evidence.append({
                "group_id": group.group_id,
                "label": group.label,
                "semantic_role": group.semantic_role,
                "requested_name": selected_requested,
                "candidate_names": list(candidates),
                "resolved_name": resolved_name,
                "asset_path": str(selected.file_path),
                "catalog_source": selected.source,
            })

        if not resolved_groups:
            raise Stage8AssetResolutionError(
                "AI reference-image analysis produced no Plant Group with a real T2 asset match."
            )

        total = sum(max(0.0, float(group.coverage_weight)) for group in resolved_groups)
        if total <= 0.0:
            equal = 1.0 / float(len(resolved_groups))
            resolved_groups = [replace(group, coverage_weight=equal) for group in resolved_groups]
        else:
            resolved_groups = [
                replace(group, coverage_weight=max(0.0, float(group.coverage_weight)) / total)
                for group in resolved_groups
            ]

        return AIPlantGroupResolution(
            resolved_plan=replace(plan, groups=tuple(resolved_groups)),
            evidence=tuple(evidence),
            excluded_groups=tuple(excluded),
        )
