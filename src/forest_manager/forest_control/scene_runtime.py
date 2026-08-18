from __future__ import annotations

from typing import Any, Mapping

from .plant_group_execution import execute_plant_group_manifest
from .service import ForestPackControlService


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

    def execute_manifest(
        self,
        manifest: Mapping[str, Any],
        *,
        strict_acceptance: bool = True,
    ) -> dict[str, Any]:
        return execute_plant_group_manifest(
            manifest,
            service=self.service,
            strict_acceptance=strict_acceptance,
        )
