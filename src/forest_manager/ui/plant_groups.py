from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable, Mapping


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
    source_names: tuple[str, ...] = ()
    spacing_system: tuple[float, float] | None = None
    area_nodes: tuple[str, ...] = ()
    legacy_forest_name: str | None = None
    artist_values: dict[str, Any] = field(default_factory=dict)
    manifest_backed: bool = False


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


def _groups_from_manifest(
    manifest: Mapping[str, Any] | None, forest_names: Iterable[str]
) -> tuple[PlantGroupTarget, ...]:
    if not isinstance(manifest, Mapping):
        return ()
    primary = str(manifest.get("primary_forest") or PRIMARY_FOREST_NAME)
    names = tuple(str(name) for name in forest_names)
    if primary not in names:
        return ()
    raw_groups = manifest.get("groups")
    if not isinstance(raw_groups, list):
        return ()
    groups: list[PlantGroupTarget] = []
    for position, item in enumerate(raw_groups, start=1):
        if not isinstance(item, Mapping):
            continue
        group_id = str(item.get("group_id") or f"plant_group:{position}").strip()
        label = str(item.get("label") or f"Plant Group {position}").strip()
        sources = tuple(str(value) for value in (item.get("source_names") or ()) if str(value).strip())
        areas = tuple(str(value) for value in (item.get("area_nodes") or ()) if str(value).strip())
        spacing = item.get("spacing_system")
        spacing_pair = None
        if isinstance(spacing, (list, tuple)) and len(spacing) == 2:
            try:
                spacing_pair = (float(spacing[0]), float(spacing[1]))
            except (TypeError, ValueError):
                spacing_pair = None
        raw_artist_values = item.get("artist_values")
        artist_values = dict(raw_artist_values) if isinstance(raw_artist_values, Mapping) else {}
        groups.append(
            PlantGroupTarget(
                group_id=group_id,
                label=label,
                forest_name=primary,
                order=int(item.get("order") or position),
                source_names=sources,
                spacing_system=spacing_pair,
                area_nodes=areas,
                legacy_forest_name=str(item.get("legacy_forest_name") or "") or None,
                artist_values=artist_values,
                manifest_backed=True,
            )
        )
    return tuple(sorted(groups, key=lambda item: (item.order, item.label.lower())))


def discover_plant_groups(
    forest_names: Iterable[str], manifest: Mapping[str, Any] | None = None
) -> tuple[PlantGroupTarget, ...]:
    """Build a dynamic artist-facing group list from managed runtime Forests.

    No fixed group count is assumed. Legacy Stage 5/6 layer Forest names are
    translated into readable labels and kept as implementation details. If a
    scene has no managed layer Forests yet, the primary Forest is exposed as a
    single ``All Planting`` group so existing single-Forest scenes still work.
    """

    names = tuple(str(name) for name in forest_names)
    persisted = _groups_from_manifest(manifest, names)
    if persisted:
        return persisted
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
