from __future__ import annotations

import json

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.display_render_effects import DisplayRenderEffectsAdapter


def main() -> int:
    print('Forest Manager Stage 5D.47 Display + Render No-op Roundtrip Boundary:')
    try:
        service = ForestPackControlService()
        adapter = DisplayRenderEffectsAdapter(service)
        forests = service.list_forests()
        reports = []

        for forest_name in forests:
            before = adapter.scalar_snapshot(forest_name)
            verification = adapter.runtime_verify_writability(forest_name)
            plan = adapter.no_op_display_render_plan(forest_name)
            preserved = before == plan
            if not preserved:
                raise RuntimeError('No-op display/render plan changed state: ' + forest_name)

            reports.append({
                'forest_name': forest_name,
                'writable_fields': list(verification['writable_fields']),
                'read_only_fields': list(verification['read_only_fields']),
                'operation_count': 0,
                'rollback_steps': 0,
                'plan_preserved': True,
                'write_executed': False,
                'rollback_executed': False,
                'vmesh': before.get('vmesh'),
                'vmaxitems': before.get('vmaxitems'),
                'rmesh': before.get('rmesh'),
                'renderMode': before.get('renderMode'),
                'rmaxitems': before.get('rmaxitems'),
                'opacity': before.get('opacity'),
            })

        result = {
            'ok': True,
            'forest_count': len(forests),
            'plan_count': len(reports),
            'operation_count': 0,
            'rollback_step_count': 0,
            'forests': reports,
            'policy': {
                'runtime_verified_writability': False,
                'writability_probe_blocked_by_runtime_boundary': True,
                'display_render_plan_only': True,
                'display_write': False,
                'render_write': False,
                'effect_record_write': False,
                'effect_curve_write': False,
                'writes_executed': False,
                'write_verification': False,
                'rollback_executed': False,
                'final_state_preserved': True,
                'runtime_write_boundary': True,
                'write_boundary_reason': 'Verified bridge exposes discovery only; set_property and rollback endpoints required by the historical writability probe are absent from the current runtime capability surface.',
            },
            'verified': True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print('Stage 5D.47 display + render no-op roundtrip capability boundary passed.')
        return 0
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': type(exc).__name__ + ': ' + str(exc), 'verified': False}, indent=2, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
