from __future__ import annotations

from typing import Any, Mapping

from .plant_group_execution import execute_plant_group_manifest
from .service import ForestControlError, ForestPackControlService


class ForestSceneRuntime:
    """Official scene-generation facade for the current verified runtime.

    The stable runtime contract is manifest-based:
    high-level callers -> ForestSceneRuntime -> plant_group_execution
    -> ForestPackControlService -> runtime bridge -> 3ds Max.

    The incomplete Stage 8 PlantingPlan executor is intentionally not imported
    here until its missing schema/dependency set is restored and verified.
    """

    def __init__(
        self,
        *,
        service: ForestPackControlService | None = None,
    ) -> None:
        self.service = service or ForestPackControlService()

    @staticmethod
    def _manifest_forest_name(manifest: Mapping[str, Any]) -> str:
        return str(manifest.get("primary_forest") or "FM_Forest_001").strip() or "FM_Forest_001"

    def _geometry_source_count(self, forest_name: str) -> int:
        inventory = self.service.inventory(forest_name, preflight=False)
        cobj = next(
            (
                item
                for item in (inventory.get("properties") or [])
                if isinstance(item, dict) and str(item.get("name") or "").lower() == "cobjlist"
            ),
            None,
        )
        metadata = cobj.get("array_metadata") if isinstance(cobj, dict) else None
        count = int((metadata or {}).get("count") or 0) if isinstance(metadata, dict) else 0
        if count < 0:
            raise ForestControlError("Geometry-source count cannot be negative.")
        return count

    def execute_manifest(
        self,
        manifest: Mapping[str, Any],
        *,
        strict_acceptance: bool = True,
    ) -> dict[str, Any]:
        forest_name = self._manifest_forest_name(manifest)
        before_source_count = self._geometry_source_count(forest_name)

        result = execute_plant_group_manifest(
            manifest,
            service=self.service,
            strict_acceptance=strict_acceptance,
        )

        after_source_count = self._geometry_source_count(forest_name)
        if after_source_count != before_source_count:
            raise ForestControlError(
                "Official manifest execution changed the Geometry source count: "
                f"forest={forest_name} before={before_source_count} after={after_source_count}. "
                "Manifest execution must reuse the existing managed source set."
            )
        return result
