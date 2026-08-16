from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .service import ForestPackControlService

DISPLAY_FIELDS = (
    'vmesh', 'geomtexid', 'vtype', 'adaptfaces', 'cloudcolorid', 'cloudens', 'vmaxitems'
)

RENDER_FIELDS = (
    'rmesh', 'rskip', 'opacity', 'wireFrame', 'rtype', 'renderMode', 'rmaxitems', 'maxfaces'
)

EFFECT_RECORD_FIELDS = (
    'efidlist', 'efnamelist', 'efxmllist', 'efenablelist', 'efselspeclist', 'efspeclist',
    'efpaid', 'efpaeffid', 'efpatype', 'efpaname', 'efpalimit', 'efpadesc', 'efpanumtype',
    'efpaintval', 'efpaintmin', 'efpaintmax', 'efpaintdef', 'efpafloatval', 'efpafloatmin',
    'efpafloatmax', 'efpafloatdef', 'efpaunitval', 'efpaunitmin', 'efpaunitmax', 'efpaunitdef',
    'efpainode', 'efpaspline', 'efpacontref', 'efpacontanim', 'efpacontype', 'efpatexmap',
    'efpacurve',
)

EFFECT_CURVE_FIELDS = ('Effect_Curves',)
DISPLAY_RENDER_FIELDS = DISPLAY_FIELDS + RENDER_FIELDS


@dataclass(frozen=True)
class DisplayRenderEffectsState:
    forest_name: str
    display: Mapping[str, Any]
    render: Mapping[str, Any]
    effect_records: Mapping[str, Any]
    effect_curves: Mapping[str, Any]


class DisplayRenderEffectsAdapter:
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

    def read_state(self, forest_name: str) -> DisplayRenderEffectsState:
        values = self._inventory_values(forest_name)
        return DisplayRenderEffectsState(
            forest_name=forest_name,
            display=self._read_group(values, DISPLAY_FIELDS),
            render=self._read_group(values, RENDER_FIELDS),
            effect_records=self._read_group(values, EFFECT_RECORD_FIELDS),
            effect_curves=self._read_group(values, EFFECT_CURVE_FIELDS),
        )

    def runtime_verify_writability(self, forest_name: str) -> dict[str, Any]:
        self.read_state(forest_name)
        return {
            'writable_fields': (),
            'read_only_fields': DISPLAY_RENDER_FIELDS,
            'operation_count': 0,
            'runtime_probe_executed': False,
            'runtime_write_boundary': True,
        }

    def scalar_snapshot(
        self,
        forest_name: str,
        fields: tuple[str, ...] = DISPLAY_RENDER_FIELDS,
    ) -> dict[str, Any]:
        state = self.read_state(forest_name)
        merged: dict[str, Any] = {}
        merged.update(state.display)
        merged.update(state.render)
        return {prop: merged.get(prop) for prop in fields}

    def no_op_display_render_plan(self, forest_name: str) -> dict[str, Any]:
        return dict(self.scalar_snapshot(forest_name, DISPLAY_RENDER_FIELDS))
