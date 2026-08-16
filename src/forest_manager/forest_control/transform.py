from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .service import ForestPackControlService

TRANSLATION_FIELDS: tuple[str, ...] = (
    'applytranslation','transxmin','transymin','transzmin','transxmax','transymax','transzmax',
    'transmapx','transmapy','transmapz','transmap','transmapchan','transcolormap','transprobmap',
)
ROTATION_FIELDS: tuple[str, ...] = (
    'applyrotation','xrotmin','xrotmax','yrotmin','yrotmax','zrotmin','zrotmax','rotmapx','rotmapy','rotmapz',
    'userotprobcurve','rotprobcurve','rotmap','rotmapchan','rotcolormap','rotprobmap',
)
SCALE_FIELDS: tuple[str, ...] = (
    'applyscale','scalexmax','scalexmin','scaleymax','scaleymin','scalezmax','scalezmin','scamapx','scamapy','scamapz',
    'usescaprobcurve','scaprobcurve','scamap','scamapchan','scacolormap','scaprobmap','scalelock',
)
OPAQUE_CURVE_FIELDS: tuple[str, ...] = ('rotprobcurve','scaprobcurve')
COMPLEX_TRANSFORM_FIELDS: tuple[str, ...] = ('transmap','rotmap','scamap','rotprobcurve','scaprobcurve')
WRITABLE_TRANSFORM_SCALARS: tuple[str, ...] = tuple(
    field for field in TRANSLATION_FIELDS + ROTATION_FIELDS + SCALE_FIELDS
    if field not in COMPLEX_TRANSFORM_FIELDS
)

@dataclass(frozen=True)
class TransformState:
    forest_name: str
    translation: Mapping[str, Any]
    rotation: Mapping[str, Any]
    scale: Mapping[str, Any]


def _unwrap_property(entry: Mapping[str, Any]) -> Any:
    if 'value' in entry:
        return entry.get('value')
    prop = entry.get('property')
    if isinstance(prop, Mapping) and 'value' in prop:
        return prop.get('value')
    return None


class TransformAdapter:
    def __init__(self, service: ForestPackControlService | None = None) -> None:
        self.service = service or ForestPackControlService()

    def _inventory_values(self, forest_name: str) -> dict[str, Any]:
        inventory = self.service.inventory(forest_name)
        values: dict[str, Any] = {}
        for entry in inventory.get('properties') or []:
            if not isinstance(entry, Mapping):
                continue
            name = entry.get('name')
            if isinstance(name, str):
                values[name] = _unwrap_property(entry)
        return values

    def _read_group(self, forest_name: str, fields: tuple[str, ...], inventory_values: Mapping[str, Any] | None = None) -> dict[str, Any]:
        values = dict(inventory_values or self._inventory_values(forest_name))
        return {prop: values.get(prop) for prop in fields}

    def read_state(self, forest_name: str) -> TransformState:
        values = self._inventory_values(forest_name)
        return TransformState(
            forest_name=forest_name,
            translation=self._read_group(forest_name, TRANSLATION_FIELDS, values),
            rotation=self._read_group(forest_name, ROTATION_FIELDS, values),
            scale=self._read_group(forest_name, SCALE_FIELDS, values),
        )

    def scalar_snapshot(self, forest_name: str) -> dict[str, Any]:
        state = self.read_state(forest_name)
        merged: dict[str, Any] = {}
        merged.update(state.translation)
        merged.update(state.rotation)
        merged.update(state.scale)
        return {prop: merged.get(prop) for prop in WRITABLE_TRANSFORM_SCALARS}

    def no_op_scalar_plan(self, forest_name: str) -> dict[str, Any]:
        return dict(self.scalar_snapshot(forest_name))
