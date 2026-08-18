from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .service import ForestControlError, ForestPackControlService

GEOMETRY_SOURCE_ARRAYS: tuple[str, ...] = (
    "cobjlist", "matlist", "namelist", "coloridlist", "geomlist", "tempidlist",
    "tempnamelist", "widthlist", "heightlist", "ScaleList", "zoffsetlist",
    "centerlist", "radiuslist", "specidlist", "usemeshdimlist", "conamelist",
    "includechildlist", "keepgrouplist", "nongeomlist", "old_problist", "problist",
)


@dataclass(frozen=True)
class GeometrySourceRecord:
    index: int
    source_node: str | None
    material_name: str | None
    name: str
    geometry_id: int
    temp_id: int
    temp_name: str
    width: float
    height: float
    scale: float
    z_offset: float
    center: int
    radius: int
    species_id: int
    use_mesh_dimensions: bool
    custom_object_name: str
    include_children: bool
    keep_group: bool
    non_geometry: bool
    old_probability: int
    probability: float
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class GeometrySourcePatch:
    source_node: str | None = None
    material_name: str | None = None
    name: str | None = None
    geometry_id: int | None = None
    temp_id: int | None = None
    temp_name: str | None = None
    width: float | None = None
    height: float | None = None
    scale: float | None = None
    z_offset: float | None = None
    center: int | None = None
    radius: int | None = None
    species_id: int | None = None
    use_mesh_dimensions: bool | None = None
    custom_object_name: str | None = None
    include_children: bool | None = None
    keep_group: bool | None = None
    non_geometry: bool | None = None
    old_probability: int | None = None
    probability: float | None = None


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
    text = str(value or "").strip().lower()
    return text in {"true", "1", "yes", "on"}


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
    return text.strip() or None


def _material_ref_name(value: Any) -> str | None:
    text = _raw_ref_text(value)
    if not text:
        return None
    if text.startswith("#"):
        body = text[1:]
        if ":" in body:
            body = body.split(":", 1)[1]
        if "(" in body:
            body = body.split("(", 1)[0]
        return body.strip() or None
    return text.strip() or None


class GeometrySourcesAdapter:
    """Geometry List adapter constrained to verified bridge capability.

    Complete reads use the verified FOREST_CONTROL_GET_ARRAY_ELEMENT endpoint.
    Writes remain governed by the explicit verified write surface and are never
    simulated from discovery metadata.
    """

    def __init__(self, service: ForestPackControlService | None = None) -> None:
        self.service = service or ForestPackControlService()

    def read_raw_record(self, forest_name: str, index: int) -> dict[str, Any]:
        """Read one complete Geometry List record through verified array endpoints.

        The public adapter remains 1-based because Forest Pack Geometry List rows
        are presented that way to the rest of Forest Manager. The bridge endpoint
        is explicitly zero-based, so the conversion happens exactly once here.

        Discovery array previews are intentionally not used: they expose only a
        bounded diagnostic prefix and are not a complete runtime record API.
        """
        if isinstance(index, bool) or not isinstance(index, int):
            raise ForestControlError("Geometry source index must be an integer.")
        if index < 1:
            raise ForestControlError("Geometry source indices are 1-based.")

        zero_index = index - 1
        first = self.service.get_array_element(
            forest_name,
            "cobjlist",
            zero_index,
            preflight=True,
        )
        count = int(first.get("count") or 0)
        if index > count:
            raise ForestControlError(
                f"Geometry source index out of range: {forest_name}[{index}] count={count}"
            )

        raw: dict[str, Any] = {"cobjlist": first.get("value")}
        for property_name in GEOMETRY_SOURCE_ARRAYS[1:]:
            element = self.service.get_array_element(
                forest_name,
                property_name,
                zero_index,
                preflight=False,
            )
            element_count = int(element.get("count") or 0)
            if element_count != count:
                raise ForestControlError(
                    "Geometry source array count mismatch: "
                    + f"{forest_name}.{property_name} count={element_count}, cobjlist count={count}"
                )
            raw[property_name] = element.get("value")
        return raw

    def read_record(self, forest_name: str, index: int) -> GeometrySourceRecord:
        raw = self.read_raw_record(forest_name, index)
        return GeometrySourceRecord(
            index=index,
            source_node=_node_ref_name(raw.get("cobjlist")),
            material_name=_material_ref_name(raw.get("matlist")),
            name=_text(raw.get("namelist")),
            geometry_id=_int(raw.get("geomlist")),
            temp_id=_int(raw.get("tempidlist")),
            temp_name=_text(raw.get("tempnamelist")),
            width=_float(raw.get("widthlist")),
            height=_float(raw.get("heightlist")),
            scale=_float(raw.get("ScaleList")),
            z_offset=_float(raw.get("zoffsetlist")),
            center=_int(raw.get("centerlist")),
            radius=_int(raw.get("radiuslist")),
            species_id=_int(raw.get("specidlist")),
            use_mesh_dimensions=_bool(raw.get("usemeshdimlist")),
            custom_object_name=_text(raw.get("conamelist")),
            include_children=_bool(raw.get("includechildlist")),
            keep_group=_bool(raw.get("keepgrouplist")),
            non_geometry=_bool(raw.get("nongeomlist")),
            old_probability=_int(raw.get("old_problist")),
            probability=_float(raw.get("problist")),
            raw=raw,
        )

    def update_existing(self, forest_name: str, index: int, patch: GeometrySourcePatch) -> dict[str, Any]:
        raise ForestControlError(
            "Geometry source atomic writes are unavailable on the verified bridge baseline; "
            "no array/reference write or rollback endpoint is exposed."
        )

    def no_op_roundtrip_plan(self, forest_name: str, index: int) -> GeometrySourcePatch:
        record = self.read_record(forest_name, index)
        return GeometrySourcePatch(
            source_node=record.source_node,
            material_name=record.material_name,
            name=record.name,
            geometry_id=record.geometry_id,
            temp_id=record.temp_id,
            temp_name=record.temp_name,
            width=record.width,
            height=record.height,
            scale=record.scale,
            z_offset=record.z_offset,
            center=record.center,
            radius=record.radius,
            species_id=record.species_id,
            use_mesh_dimensions=record.use_mesh_dimensions,
            custom_object_name=record.custom_object_name,
            include_children=record.include_children,
            keep_group=record.keep_group,
            non_geometry=record.non_geometry,
            old_probability=record.old_probability,
            probability=record.probability,
        )
