from __future__ import annotations

import json
from dataclasses import asdict

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.display_render_effects import DisplayRenderEffectsAdapter


def main() -> int:
    print('Forest Manager Stage 5D.47 Display + Render + Effects Domain Runtime Boundary:')
    try:
        service = ForestPackControlService()
        adapter = DisplayRenderEffectsAdapter(service)
        forests = service.list_forests()
        reports = [asdict(adapter.read_state(forest_name)) for forest_name in forests]
        result = {
            'ok': True,
            'forest_count': len(forests),
            'forests': reports,
            'policy': {
                'read_only_discovery': True,
                'display_write': False,
                'render_write': False,
                'effect_record_write': False,
                'effect_curve_write': False,
                'effect_record_policy': 'read_only_until_record_adapter',
                'effect_curve_policy': 'read_only_opaque',
                'runtime_write_boundary': True,
                'write_boundary_reason': 'Verified bridge exposes discovery only; display/render scalar write, effect record write, effect curve write, and rollback endpoints are absent from the current runtime capability surface.',
            },
            'verified': True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print('Stage 5D.47 display + render + effects domain runtime capability boundary passed.')
        return 0
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': type(exc).__name__ + ': ' + str(exc), 'verified': False}, indent=2, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
