from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .service import ForestPackControlService

SURFACE_FIELDS: tuple[str, ...] = (
    'surflist','surflink','altlimited','altmax','altmin','surfaltdens','surfaltscal',
    'slopelimited','slopemax','slopemin','surfslodens','surfsloscal','surfanim',
    'linkeditsurf','direction','surfmode','uvalign','uvscalex','uvscaley',
    'uvmultscalex','uvmultscaley',
)
SURFACE_CURVE_FIELDS: tuple[str, ...] = ('spdenscurve','spscalcurve','Surface_Falloff_Curves')
SURFACE_OPAQUE_CURVES = SURFACE_CURVE_FIELDS
CAMERA_FIELDS: tuple[str, ...] = (
    'camera','lookattarget','camlimit','uselookat','camlookat','camlod','camloddist',
    'camlodlookat','camwidth','camnear','camfar','cambho',
)
CAMERA_CURVE_FIELDS: tuple[str, ...] = ('camdenscurve','camscacurve')
CAMERA_OPAQUE_CURVES = CAMERA_CURVE_FIELDS
COMPLEX_SURFACE_CAMERA_FIELDS: tuple[str, ...] = ('surflist','surflink','camera','lookattarget')
WRITABLE_SURFACE_CAMERA_SCALARS: tuple[str, ...] = tuple(
    f for f in SURFACE_FIELDS + CAMERA_FIELDS if f not in COMPLEX_SURFACE_CAMERA_FIELDS
)

@dataclass(frozen=True)
class SurfaceCameraState:
    forest_name: str
    surface: Mapping[str, Any]
    surface_curves: Mapping[str, Any]
    camera: Mapping[str, Any]
    camera_curves: Mapping[str, Any]


def _inventory_values(inventory: Mapping[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for item in inventory.get('properties') or []:
        if not isinstance(item, Mapping):
            continue
        name = item.get('name')
        if not isinstance(name, str):
            continue
        if 'value' in item:
            values[name] = item.get('value')
            continue
        meta = item.get('property')
        if isinstance(meta, Mapping):
            values[name] = meta.get('value')
    return values


class SurfaceCameraAdapter:
    def __init__(self, service: ForestPackControlService | None = None) -> None:
        self.service = service or ForestPackControlService()

    def _read_group(self, values: Mapping[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
        return {prop: values.get(prop) for prop in fields}

    def read_state(self, forest_name: str) -> SurfaceCameraState:
        values = _inventory_values(self.service.inventory(forest_name))
        return SurfaceCameraState(
            forest_name=forest_name,
            surface=self._read_group(values, SURFACE_FIELDS),
            surface_curves=self._read_group(values, SURFACE_CURVE_FIELDS),
            camera=self._read_group(values, CAMERA_FIELDS),
            camera_curves=self._read_group(values, CAMERA_CURVE_FIELDS),
        )

    def scalar_snapshot(self, forest_name: str) -> dict[str, Any]:
        state = self.read_state(forest_name)
        merged: dict[str, Any] = {}
        merged.update(state.surface)
        merged.update(state.camera)
        return {prop: merged.get(prop) for prop in WRITABLE_SURFACE_CAMERA_SCALARS}

    def no_op_scalar_plan(self, forest_name: str) -> dict[str, Any]:
        return dict(self.scalar_snapshot(forest_name))
