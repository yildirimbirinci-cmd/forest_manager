from __future__ import annotations

import json

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.material_animation import MaterialAnimationAdapter

def main() -> int:
    print('Forest Manager Stage 5D.46 Material + Animation No-op Roundtrip Boundary:')
    try:
        service = ForestPackControlService()
        adapter = MaterialAnimationAdapter(service)
        forests = service.list_forests()
        reports = []
        for forest_name in forests:
            before = adapter.writable_snapshot(forest_name)
            plan = adapter.no_op_writable_plan(forest_name)
            preserved = before == plan
            if not preserved:
                raise RuntimeError('No-op material/animation plan changed state: ' + forest_name)
            reports.append({
                'forest_name': forest_name,
                'plan_preserved': True,
                'write_executed': False,
                'rollback_executed': False,
                'animation_offset': before['times'].get('animsoffset'),
                'animation_start': before['times'].get('animstart'),
                'animation_end': before['times'].get('animend'),
                'tint_color_1': before['colors'].get('tintcolor1'),
                'tint_color_2': before['colors'].get('tintcolor2'),
                'material_apply_color': before['colors'].get('matapplycolor'),
            })
        result = {
            'ok': True,
            'forest_count': len(forests),
            'plan_count': len(reports),
            'operation_count': 0,
            'rollback_step_count': 0,
            'forests': reports,
            'policy': {
                'scalar_plan_only': True,
                'scalar_write': False,
                'color_write': False,
                'time_write': False,
                'bitmap_write': False,
                'writes_executed': False,
                'write_verification': False,
                'rollback_executed': False,
                'final_state_preserved': True,
                'runtime_write_boundary': True,
                'write_boundary_reason': 'Verified bridge exposes discovery only; scalar/color/time/bitmap write and rollback endpoints are absent from the current runtime capability surface.',
            },
            'verified': True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print('Stage 5D.46 material + animation no-op roundtrip capability boundary passed.')
        return 0
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': type(exc).__name__ + ': ' + str(exc), 'verified': False}, indent=2, ensure_ascii=False))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
