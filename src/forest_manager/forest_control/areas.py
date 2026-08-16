from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .service import ForestControlError, ForestPackControlService

AREA_RECORD_ARRAYS: tuple[str, ...] = (
    "aridlist", "pf_aractivelist", "arnamelist", "arnodelist", "arnodenamelist",
    "artypelist", "arincexclist", "arresollist", "arslicelist", "arslicetoplist",
    "arwidthlist", "arforceopenlist", "armaplist", "arscalelist", "arthresholdlist",
    "arsurfidlist", "arflafdenslist", "arflafscalist", "arflinvlist", "arselspeclist",
    "arspeclist", "arpaintlist", "arboundchecklist", "arprojectlist", "arshapelist",
    "arobscalelist", "arlinkidlist", "arscalemin", "arscalemax", "arzoffset",
)


@dataclass(frozen=True)
class AreaRecord:
    index: int
    area_id: int
    active: bool
    name: str
    node_name: str | None
    node_name_cache: str
    area_type: int
    include_exclude: int
    resolution: int
    slice_enabled: bool
    slice_top: float
    width: float
    force_open: bool
    scale: float
    threshold: float
    surface_id: str
    falloff_density: float
    falloff_scale: float
    falloff_invert: bool
    select_species: bool
    species: str
    bound_check: int
    project: int
    shape: int
    obstacle_scale: float
    link_id: int
    scale_min: float
    scale_max: float
    z_offset: float
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class AreaRecordPatch:
    active: bool | None = None
    name: str | None = None
    node_name: str | None = None
    node_name_cache: str | None = None
    area_type: int | None = None
    include_exclude: int | None = None
    resolution: int | None = None
    slice_enabled: bool | None = None
    slice_top: float | None = None
    width: float | None = None
    force_open: bool | None = None
    scale: float | None = None
    threshold: float | None = None
    surface_id: str | None = None
    falloff_density: float | None = None
    falloff_scale: float | None = None
    falloff_invert: bool | None = None
    select_species: bool | None = None
    species: str | None = None
    bound_check: int | None = None
    project: int | None = None
    shape: int | None = None
    obstacle_scale: float | None = None
    link_id: int | None = None
    scale_min: float | None = None
    scale_max: float | None = None
    z_offset: float | None = None


def _preview_value(prop: Mapping[str, Any], index: int) -> Any:
    metadata = prop.get("array_metadata")
    if not isinstance(metadata, Mapping):
        return None
    elements = metadata.get("elements")
    if not isinstance(elements, list) or index < 1 or index > len(elements):
        return None
    element = elements[index - 1]
    if not isinstance(element, Mapping):
        return None
    return element.get("preview")


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _int(value: Any) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"true", "1", "yes", "on"}


def _raw_ref_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _node_ref_name(value: Any) -> str | None:
    text = _raw_ref_text(value)
    if not text:
        return None
    if text.startswith("$"):
        body = text[1:]
        if ":" in body:
            body = body.split(":", 1)[1]
        if " @ [" in body:
            body = body.split(" @ [", 1)[0]
        return body.strip() or None
    if " @ [" in text:
        text = text.split(" @ [", 1)[0]
    if ":" in text and not text.startswith(("http:", "https:")):
        maybe_class, maybe_name = text.split(":", 1)
        if maybe_class and maybe_name and " " not in maybe_class:
            text = maybe_name
    return text.strip() or None


class AreaRecordsAdapter:
    """Stage 5D.42 area-record adapter on the verified discovery-only bridge surface."""

    def __init__(self, service: ForestPackControlService | None = None) -> None:
        self.service = service or ForestPackControlService()

    def read_raw_record(self, forest_name: str, index: int) -> dict[str, Any]:
        if index < 1:
            raise ForestControlError("Area indices are 1-based.")
        inventory = self.service.inventory(forest_name)
        props = {
            str(prop.get("name") or ""): prop
            for prop in (inventory.get("properties") or [])
            if isinstance(prop, Mapping)
        }
        arid = props.get("aridlist") or {}
        metadata = arid.get("array_metadata") if isinstance(arid, Mapping) else None
        count = int((metadata or {}).get("count") or 0) if isinstance(metadata, Mapping) else 0
        if index > count:
            raise ForestControlError(f"Area index out of range: {forest_name}[{index}] count={count}")
        if index > 8:
            raise ForestControlError(
                "Current verified bridge exposes only the first 8 array elements in discovery preview."
            )
        return {name: _preview_value(props.get(name) or {}, index) for name in AREA_RECORD_ARRAYS}

    def read_record(self, forest_name: str, index: int) -> AreaRecord:
        raw = self.read_raw_record(forest_name, index)
        return AreaRecord(
            index=index,
            area_id=_int(raw.get("aridlist")),
            active=_bool(raw.get("pf_aractivelist")),
            name=_text(raw.get("arnamelist")),
            node_name=_node_ref_name(raw.get("arnodelist")),
            node_name_cache=_text(raw.get("arnodenamelist")),
            area_type=_int(raw.get("artypelist")),
            include_exclude=_int(raw.get("arincexclist")),
            resolution=_int(raw.get("arresollist")),
            slice_enabled=_bool(raw.get("arslicelist")),
            slice_top=_float(raw.get("arslicetoplist")),
            width=_float(raw.get("arwidthlist")),
            force_open=_bool(raw.get("arforceopenlist")),
            scale=_float(raw.get("arscalelist")),
            threshold=_float(raw.get("arthresholdlist")),
            surface_id=_text(raw.get("arsurfidlist")),
            falloff_density=_float(raw.get("arflafdenslist")),
            falloff_scale=_float(raw.get("arflafscalist")),
            falloff_invert=_bool(raw.get("arflinvlist")),
            select_species=_bool(raw.get("arselspeclist")),
            species=_text(raw.get("arspeclist")),
            bound_check=_int(raw.get("arboundchecklist")),
            project=_int(raw.get("arprojectlist")),
            shape=_int(raw.get("arshapelist")),
            obstacle_scale=_float(raw.get("arobscalelist")),
            link_id=_int(raw.get("arlinkidlist")),
            scale_min=_float(raw.get("arscalemin")),
            scale_max=_float(raw.get("arscalemax")),
            z_offset=_float(raw.get("arzoffset")),
            raw=raw,
        )

    def update_existing(self, forest_name: str, index: int, patch: AreaRecordPatch) -> dict[str, Any]:
        raise ForestControlError(
            "Area record atomic writes are unavailable on the verified bridge baseline; "
            "no array/reference write or rollback endpoint is exposed."
        )

    def no_op_roundtrip_plan(self, forest_name: str, index: int) -> AreaRecordPatch:
        record = self.read_record(forest_name, index)
        return AreaRecordPatch(
            active=record.active,
            name=record.name,
            node_name=record.node_name,
            node_name_cache=record.node_name_cache,
            area_type=record.area_type,
            include_exclude=record.include_exclude,
            resolution=record.resolution,
            slice_enabled=record.slice_enabled,
            slice_top=record.slice_top,
            width=record.width,
            force_open=record.force_open,
            scale=record.scale,
            threshold=record.threshold,
            surface_id=record.surface_id,
            falloff_density=record.falloff_density,
            falloff_scale=record.falloff_scale,
            falloff_invert=record.falloff_invert,
            select_species=record.select_species,
            species=record.species,
            bound_check=record.bound_check,
            project=record.project,
            shape=record.shape,
            obstacle_scale=record.obstacle_scale,
            link_id=record.link_id,
            scale_min=record.scale_min,
            scale_max=record.scale_max,
            z_offset=record.z_offset,
        )
