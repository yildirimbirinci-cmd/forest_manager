from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from forest_manager.forest_control.service import ForestControlError
from forest_manager.forest_control.semantic_transaction import UnifiedControlOperation


@dataclass(frozen=True)
class SemanticCandidatePlan:
    key: str
    label: str
    choice: str
    operations: tuple[UnifiedControlOperation, ...]
    blocked_reasons: tuple[str, ...] = ()
    status: str = "candidate"

    @property
    def executable(self) -> bool:
        return bool(self.operations) and not self.blocked_reasons


# Candidate calibration profiles. These are not final visual presets.
NATURALNESS_CANDIDATES: dict[str, dict[str, bool | int | float]] = {
    "Ordered": {"clurough": 0.0, "clunoise": 0.0, "cluedge": 0.0, "drotation": 0.0, "divers": 0, "distpathrandpos": 0.0},
    "Balanced": {"clurough": 5.0, "clunoise": 5.0, "cluedge": 5.0, "drotation": 10.0, "divers": 10, "distpathrandpos": 5.0},
    "Natural": {"clurough": 15.0, "clunoise": 20.0, "cluedge": 15.0, "drotation": 30.0, "divers": 25, "distpathrandpos": 15.0},
    "Wild": {"clurough": 30.0, "clunoise": 40.0, "cluedge": 25.0, "drotation": 60.0, "divers": 40, "distpathrandpos": 30.0},
}

# Stage 7.8 profiles use display-meter intent for cluster size, then convert through
# the active scene-unit context before creating raw Forest Pack operations.
# Forest Pack documents cluster size in scene units and roughness/noise/edge in 0..100%.
CLUSTER_CHARACTER_CANDIDATES: dict[str, dict[str, float]] = {
    "Small Groups": {"size_m": 10.0, "clurough": 10.0, "clunoise": 5.0, "cluedge": 10.0},
    "Medium Clusters": {"size_m": 20.0, "clurough": 20.0, "clunoise": 10.0, "cluedge": 20.0},
    "Large Masses": {"size_m": 40.0, "clurough": 30.0, "clunoise": 20.0, "cluedge": 30.0},
}


class SemanticCalibrationPlanner:
    def __init__(self, controller: Any) -> None:
        self.controller = controller

    def _rows(self) -> dict[str, Any]:
        return {row.name.lower(): row for row in self.controller.state.properties}

    def plan(self, key: str, choice: str) -> SemanticCandidatePlan:
        if key == "naturalness":
            return self._naturalness(choice)
        if key == "variation":
            return self._variation(choice)
        if key == "cluster_character":
            return self._cluster_character(choice)
        raise ForestControlError(f"No semantic calibration planner for control: {key}")

    def _naturalness(self, choice: str) -> SemanticCandidatePlan:
        profile = NATURALNESS_CANDIDATES.get(choice)
        if profile is None:
            raise ForestControlError(f"Unknown Naturalness candidate: {choice}")
        rows = self._rows()
        operations: list[UnifiedControlOperation] = []
        blocked: list[str] = []
        for property_name, value in profile.items():
            row = rows.get(property_name.lower())
            if row is None:
                continue
            if not row.writable:
                blocked.append(f"{row.name}:read_only")
                continue
            operations.append(UnifiedControlOperation(property_name=row.name, value=value, label="semantic:naturalness"))
        if not operations:
            blocked.append("no_writable_naturalness_properties")
        return SemanticCandidatePlan("naturalness", "Naturalness", choice, tuple(operations), tuple(blocked))

    def _variation(self, choice: str) -> SemanticCandidatePlan:
        rows = self._rows()
        blocked: list[str] = []
        for name in ("applytranslation", "applyrotation", "applyscale"):
            row = rows.get(name)
            if row is None:
                blocked.append(f"{name}:missing")
            elif not row.writable:
                blocked.append(f"{row.name}:read_only")
            elif row.value is not True:
                blocked.append(f"{row.name}:disabled")
        return SemanticCandidatePlan("variation", "Variation", choice, (), tuple(blocked or ["variation_profile_not_calibrated"]))

    def _cluster_character(self, choice: str) -> SemanticCandidatePlan:
        if choice == "Solitary":
            return SemanticCandidatePlan(
                "cluster_character",
                "Cluster Character",
                choice,
                (),
                ("solitary_requires_cluster_disable_or_distribution_mode_capability",),
            )
        profile = CLUSTER_CHARACTER_CANDIDATES.get(choice)
        if profile is None:
            raise ForestControlError(f"Unknown Cluster Character candidate: {choice}")

        rows = self._rows()
        operations: list[UnifiedControlOperation] = []
        blocked: list[str] = []
        size_row = rows.get("clusize")
        if size_row is None:
            blocked.append("clusize:missing")
        elif not size_row.writable:
            blocked.append(f"{size_row.name}:read_only")
        else:
            size_system = self.controller._display_distance_to_system(profile["size_m"], self.controller.state.scene_units)
            operations.append(UnifiedControlOperation(property_name=size_row.name, value=size_system, label="semantic:cluster_character"))

        for property_name in ("clurough", "clunoise", "cluedge"):
            row = rows.get(property_name)
            if row is None:
                blocked.append(f"{property_name}:missing")
                continue
            if not row.writable:
                blocked.append(f"{row.name}:read_only")
                continue
            operations.append(UnifiedControlOperation(property_name=row.name, value=profile[property_name], label="semantic:cluster_character"))

        if not operations:
            blocked.append("no_writable_cluster_character_properties")
        return SemanticCandidatePlan("cluster_character", "Cluster Character", choice, tuple(operations), tuple(blocked))
