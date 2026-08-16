from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ArtistControlSpec:
    key: str
    label: str
    kind: str
    description: str
    dependent_properties: tuple[str, ...]
    options: tuple[str, ...] = ()
    direct_write: bool = False


@dataclass(frozen=True)
class ArtistControlState:
    key: str
    label: str
    kind: str
    value: Any
    description: str
    dependent_properties: tuple[str, ...]
    direct_write: bool
    available: bool
    affected_properties: tuple[str, ...] = ()
    display_suffix: str = ""
    calibration_status: str = "intent"


ARTIST_CONTROL_SPECS: tuple[ArtistControlSpec, ...] = (
    ArtistControlSpec(
        "density_spacing",
        "Plant Spacing",
        "distance",
        "Controls the X/Y distribution spacing as one synchronized physical value.",
        ("units_x", "units_y", "lock_ratio"),
        direct_write=True,
    ),
    ArtistControlSpec(
        "naturalness",
        "Naturalness",
        "choice",
        "Overall regular-to-natural planting character. The planner coordinates clustering, rotation and positional variation.",
        ("clurough", "clunoise", "cluedge", "drotation", "divers", "distrefrandpos", "distpathrandpos"),
        ("Ordered", "Balanced", "Natural", "Wild"),
        direct_write=True,
    ),
    ArtistControlSpec(
        "cluster_character",
        "Cluster Character",
        "choice",
        "Controls whether planting reads as individuals, small groups, medium clusters or broad masses.",
        ("clusize", "clurough", "clunoise", "cluedge", "problist"),
        ("Solitary", "Small Groups", "Medium Clusters", "Large Masses"),
        direct_write=True,
    ),
    ArtistControlSpec(
        "variation",
        "Variation",
        "choice",
        "Coordinates scale, rotation and translation variation instead of exposing each range separately.",
        ("applytranslation", "transxmin", "transxmax", "transymin", "transymax", "applyrotation", "zrotmin", "zrotmax", "applyscale", "scalexmin", "scalexmax", "scaleymin", "scaleymax", "scalezmin", "scalezmax"),
        ("Low", "Moderate", "High", "Very High"),
    ),
    ArtistControlSpec(
        "species_diversity",
        "Species Diversity",
        "choice",
        "Controls visual species mixing and probability balance as one intent.",
        ("divers", "problist", "geomlist", "specidlist"),
        ("Uniform", "Low", "Balanced", "Rich"),
    ),
    ArtistControlSpec(
        "boundary_behavior",
        "Boundary Behavior",
        "choice",
        "Controls how planting meets paths, walls, lawns and other contextual edges.",
        ("cluedge", "arboundchecklist", "arwidthlist", "arscalelist", "arthresholdlist"),
        ("Clean Edge", "Soft Edge", "Natural Spill", "Dense Screen"),
    ),
    ArtistControlSpec(
        "height_character",
        "Height Character",
        "choice",
        "Coordinates source scale and height variation into a single visual-height intent.",
        ("globscale", "globsize", "height", "scalezmin", "scalezmax", "ScaleList"),
        ("Low", "Medium", "Tall", "Layered"),
    ),
    ArtistControlSpec(
        "ground_visibility",
        "Ground Visibility",
        "choice",
        "Controls how open or covered the planting should read without exposing multiple density/coverage controls.",
        ("units_x", "units_y", "threshold", "maxdensity", "spdensact", "surfaltdens", "surfslodens"),
        ("Open", "Balanced", "Covered", "Closed"),
    ),
)


def default_artist_values() -> dict[str, Any]:
    return {
        "density_spacing": None,
        "naturalness": "Balanced",
        "cluster_character": "Medium Clusters",
        "variation": "Moderate",
        "species_diversity": "Balanced",
        "boundary_behavior": "Soft Edge",
        "height_character": "Layered",
        "ground_visibility": "Balanced",
    }


def artist_control_specs() -> tuple[ArtistControlSpec, ...]:
    return ARTIST_CONTROL_SPECS


def calibration_probe_keys() -> tuple[str, ...]:
    return ("naturalness", "variation", "cluster_character")
