from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .service import ForestControlError, ForestPackControlService


class SceneStateGateway:
    """Single gateway for the scene-persisted Plant Group manifest.

    The 3ds Max manifest is authoritative. UI pending edits and runtime caches are
    non-authoritative projections; persisted manifest reads, verified writes, and
    rollback snapshots pass through this gateway.
    """

    def __init__(self, service: ForestPackControlService) -> None:
        self.service = service

    def read_manifest(self, *, preflight: bool = False) -> dict[str, Any]:
        manifest = self.service.read_plant_group_manifest(preflight=preflight)
        if not isinstance(manifest, dict):
            raise ForestControlError("Plant-group manifest is missing or invalid.")
        return manifest

    def snapshot_and_working_copy(
        self, *, preflight: bool = False
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        snapshot = deepcopy(self.read_manifest(preflight=preflight))
        return snapshot, deepcopy(snapshot)

    def write_verified(
        self,
        manifest: Mapping[str, Any],
        *,
        preflight: bool = False,
        error_message: str = "Plant-group manifest write was not verified.",
    ) -> dict[str, Any]:
        result = self.service.write_plant_group_manifest(dict(manifest), preflight=preflight)
        if result.get("verified") is not True:
            raise ForestControlError(error_message)
        return result

    def restore_snapshot(
        self, snapshot: Mapping[str, Any], *, preflight: bool = False
    ) -> dict[str, Any]:
        return self.write_verified(
            snapshot,
            preflight=preflight,
            error_message="Plant-group manifest rollback was not verified.",
        )

    @staticmethod
    def groups(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
        raw_groups = manifest.get("groups")
        if not isinstance(raw_groups, list):
            raise ForestControlError("Plant-group manifest is missing or invalid.")
        return [item for item in raw_groups if isinstance(item, dict)]

    @classmethod
    def group_payload(cls, manifest: Mapping[str, Any], group_id: str) -> dict[str, Any]:
        target = next(
            (item for item in cls.groups(manifest) if str(item.get("group_id") or "") == group_id),
            None,
        )
        if target is None:
            raise ForestControlError(f"Plant group is missing from the scene manifest: {group_id}")
        return target

    def read_group(
        self, group_id: str, *, preflight: bool = False
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        manifest = self.read_manifest(preflight=preflight)
        return manifest, self.group_payload(manifest, group_id)
