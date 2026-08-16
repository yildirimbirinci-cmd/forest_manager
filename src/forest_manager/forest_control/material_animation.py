from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .service import ForestPackControlService

TINT_FIELDS = (
    'tintmixmode','tintcolor1','tintcolor2','tintmin','tintmax','tintmode','tintmap','tintmapmode','tintmapchan'
)
MATERIAL_ADJUSTMENT_FIELDS = (
    'mathue','matsaturation','matbrightness','matapply','matapplycolor','matrangewidth'
)
ANIMATION_FIELDS = (
    'animation','animsoffset','animsamples','animonlyrend','animap','animapchan','animstart','animend'
)
COLOR_FIELDS = ('tintcolor1','tintcolor2','matapplycolor')
TIME_FIELDS = ('animsoffset','animstart','animend')
BITMAP_FIELDS = ('tintmap','animap')
COMPLEX_MATERIAL_ANIMATION_FIELDS = COLOR_FIELDS + TIME_FIELDS + BITMAP_FIELDS
WRITABLE_SCALAR_FIELDS = tuple(
    f for f in TINT_FIELDS + MATERIAL_ADJUSTMENT_FIELDS + ANIMATION_FIELDS
    if f not in COMPLEX_MATERIAL_ANIMATION_FIELDS
)

@dataclass(frozen=True)
class MaterialAnimationState:
    forest_name: str
    tint: Mapping[str, Any]
    material_adjustment: Mapping[str, Any]
    animation: Mapping[str, Any]

class MaterialAnimationAdapter:
    def __init__(self, service: ForestPackControlService | None = None) -> None:
        self.service = service or ForestPackControlService()

    def _inventory_values(self, forest_name: str) -> dict[str, Any]:
        payload = self.service.inventory(forest_name)
        props = payload.get('properties') or []
        result: dict[str, Any] = {}
        for item in props:
            name = item.get('name')
            if name:
                result[str(name)] = item.get('value')
        return result

    @staticmethod
    def _read_group(values: Mapping[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
        return {field: values.get(field) for field in fields}

    def read_state(self, forest_name: str) -> MaterialAnimationState:
        values = self._inventory_values(forest_name)
        return MaterialAnimationState(
            forest_name=forest_name,
            tint=self._read_group(values, TINT_FIELDS),
            material_adjustment=self._read_group(values, MATERIAL_ADJUSTMENT_FIELDS),
            animation=self._read_group(values, ANIMATION_FIELDS),
        )

    def writable_snapshot(self, forest_name: str) -> dict[str, Any]:
        state = self.read_state(forest_name)
        merged: dict[str, Any] = {}
        merged.update(state.tint)
        merged.update(state.material_adjustment)
        merged.update(state.animation)
        return {
            'scalars': {p: merged.get(p) for p in WRITABLE_SCALAR_FIELDS},
            'colors': {p: merged.get(p) for p in COLOR_FIELDS},
            'times': {p: merged.get(p) for p in TIME_FIELDS},
        }

    def no_op_writable_plan(self, forest_name: str) -> dict[str, Any]:
        snap = self.writable_snapshot(forest_name)
        return {
            'scalars': dict(snap['scalars']),
            'colors': dict(snap['colors']),
            'times': dict(snap['times']),
        }
