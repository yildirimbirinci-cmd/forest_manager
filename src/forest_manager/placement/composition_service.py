from __future__ import annotations

from dataclasses import dataclass

from forest_manager.max_bridge.client import MaxBridgeClient
from forest_manager.t2_bridge import T2AssetCatalog, T2AssetRecord

from .composition_plan import CompositionPlan


@dataclass(frozen=True)
class ResolvedCompositionItem:
    query: str
    probability: float
    asset: T2AssetRecord


class CompositionPlanError(RuntimeError):
    pass


class CompositionPlanService:
    def __init__(
        self,
        catalog: T2AssetCatalog | None = None,
        client: MaxBridgeClient | None = None,
    ):
        self.catalog = catalog or T2AssetCatalog()
        self.client = client or MaxBridgeClient()

    def resolve(self, plan: CompositionPlan) -> list[ResolvedCompositionItem]:
        probabilities = plan.normalized_probabilities
        resolved: list[ResolvedCompositionItem] = []

        for item, probability in zip(plan.items, probabilities):
            matches = self.catalog.search_max_assets(
                item.query,
                limit=20,
                require_existing_file=True,
            )
            if not matches:
                raise CompositionPlanError(
                    f"No T2 .max asset matched composition query: {item.query}"
                )

            resolved.append(
                ResolvedCompositionItem(
                    query=item.query,
                    probability=probability,
                    asset=matches[0],
                )
            )

        names = [item.asset.name.casefold() for item in resolved]
        if len(set(names)) != len(names):
            raise CompositionPlanError(
                "Composition queries resolved to duplicate T2 assets."
            )

        return resolved

    def apply(self, plan: CompositionPlan) -> dict:
        resolved = self.resolve(plan)

        summary = self.client.get_forest_geometry_summary()
        if not summary.ok:
            raise CompositionPlanError(summary.error)

        current_names = list(summary.data.get("geometry_names") or [])
        current_by_key = {
            str(name).casefold(): index
            for index, name in enumerate(current_names)
            if str(name).strip()
        }

        planned_names = [item.asset.name for item in resolved]
        planned_keys = {name.casefold() for name in planned_names}
        unmanaged = [
            name
            for name in current_names
            if str(name).strip() and str(name).casefold() not in planned_keys
        ]
        if unmanaged:
            raise CompositionPlanError(
                "Forest contains Geometry items outside the composition plan: "
                + ", ".join(unmanaged)
            )

        added: list[str] = []

        for item in resolved:
            key = item.asset.name.casefold()
            if key in current_by_key:
                continue

            response = self.client.append_t2_asset_geometry(
                str(item.asset.file_path),
                probability=item.probability,
            )
            if not response.ok:
                raise CompositionPlanError(response.error)

            added.append(item.asset.name)

            summary = self.client.get_forest_geometry_summary()
            if not summary.ok:
                raise CompositionPlanError(summary.error)
            current_names = list(summary.data.get("geometry_names") or [])
            current_by_key = {
                str(name).casefold(): index
                for index, name in enumerate(current_names)
                if str(name).strip()
            }

        final_summary = self.client.get_forest_geometry_summary()
        if not final_summary.ok:
            raise CompositionPlanError(final_summary.error)

        final_names = list(final_summary.data.get("geometry_names") or [])
        final_keys = [str(name).casefold() for name in final_names]

        if set(final_keys) != planned_keys:
            raise CompositionPlanError(
                "Forest Geometry set does not match the composition plan."
            )

        probability_by_key = {
            item.asset.name.casefold(): item.probability
            for item in resolved
        }
        ordered_probabilities = [
            probability_by_key[key]
            for key in final_keys
        ]

        probability_result = self.client.set_geometry_probabilities(
            ordered_probabilities
        )
        if not probability_result.ok:
            raise CompositionPlanError(probability_result.error)

        reference_result = self.client.normalize_reference_sources()
        if not reference_result.ok:
            raise CompositionPlanError(reference_result.error)

        return {
            "plan_name": plan.name,
            "planned_assets": planned_names,
            "added_assets": added,
            "geometry_names": probability_result.data.get("geometry_names", []),
            "probabilities": probability_result.data.get("probabilities", []),
            "probability_total": probability_result.data.get("probability_total", 0),
            "reference_layer": reference_result.data.get("layer_name"),
            "reference_layer_visible": reference_result.data.get("layer_visible"),
            "reference_target_z_mm": reference_result.data.get("target_z_mm"),
            "verified": bool(
                probability_result.data.get("verified")
                and reference_result.data.get("verified")
            ),
        }
