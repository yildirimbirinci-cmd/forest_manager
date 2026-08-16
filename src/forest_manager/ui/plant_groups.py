from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


PRIMARY_FOREST_NAME = "FM_Forest_001"
_LAYER_PATTERN = re.compile(r"^FM_Layer_(?P<index>\d+)(?:_(?P<label>.+))?$")


@dataclass(frozen=True)
class PlantGroupTarget:
    """Artist-facing planting group mapped to one technical Forest target.

    Forest Pack exposes several distribution controls at Forest-object scope.
    Forest Manager therefore keeps the artist-facing group concept separate
    from the technical Forest object used to execute those controls.
    """

    group_id: str
    label: str
    forest_name: str
    order: int


def _humanize(value: str) -> str:
    text = re.sub(r"[_\-]+", " ", value).strip()
    text = re.sub(r"\s+", " ", text)
    return text.title() if text else "Plant Group"


def discover_primary_forest(forest_names: Iterable[str]) -> str | None:
    names = tuple(str(name) for name in forest_names)
    if PRIMARY_FOREST_NAME in names:
        return PRIMARY_FOREST_NAME
    for name in names:
        if name.startswith("FM_Forest_"):
            return name
    return names[0] if names else None


def discover_plant_groups(forest_names: Iterable[str]) -> tuple[PlantGroupTarget, ...]:
    """Build a dynamic artist-facing group list from managed runtime Forests.

    No fixed group count is assumed. Legacy Stage 5/6 layer Forest names are
    translated into readable labels and kept as implementation details. If a
    scene has no managed layer Forests yet, the primary Forest is exposed as a
    single ``All Planting`` group so existing single-Forest scenes still work.
    """

    names = tuple(str(name) for name in forest_names)
    groups: list[PlantGroupTarget] = []
    for position, name in enumerate(names):
        match = _LAYER_PATTERN.match(name)
        if match is None:
            continue
        index = int(match.group("index"))
        label = _humanize(match.group("label") or f"Plant Group {index}")
        groups.append(
            PlantGroupTarget(
                group_id=f"managed:{name}",
                label=label,
                forest_name=name,
                order=index,
            )
        )

    if groups:
        return tuple(sorted(groups, key=lambda item: (item.order, item.forest_name.lower())))

    primary = discover_primary_forest(names)
    if primary is None:
        return ()
    return (
        PlantGroupTarget(
            group_id=f"managed:{primary}",
            label="All Planting",
            forest_name=primary,
            order=0,
        ),
    )


def find_group_for_forest(
    groups: Iterable[PlantGroupTarget], forest_name: str | None
) -> PlantGroupTarget | None:
    if not forest_name:
        return None
    for group in groups:
        if group.forest_name == forest_name:
            return group
    return None
