from __future__ import annotations

import json

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.transform import TransformAdapter


def main() -> int:
    print('Forest Manager Stage 5D.44 Transform Scalar No-op Roundtrip Boundary:')
    try:
        service = ForestPackControlService()
        adapter = TransformAdapter(service)
        forests = service.list_forests()
        reports = []
        for forest_name in forests:
            before = adapter.scalar_snapshot(forest_name)
            plan = adapter.no_op_scalar_plan(forest_name)
            plan_preserved = before == plan
            if not plan_preserved:
                raise RuntimeError(f'No-op transform plan differs from current state: {forest_name}')
            reports.append({
                'forest_name': forest_name,
                'plan_preserved': True,
                'write_executed': False,
                'rollback_executed': False,
                'applytranslation': before.get('applytranslation'),
                'translation_x': [before.get('transxmin'), before.get('transxmax')],
                'applyrotation': before.get('applyrotation'),
                'rotation_z': [before.get('zrotmin'), before.get('zrotmax')],
                'applyscale': before.get('applyscale'),
                'scale_x': [before.get('scalexmin'), before.get('scalexmax')],
                'scalelock': before.get('scalelock'),
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
                'scalar_write_only': False,
                'bitmap_write': False,
                'curve_control_write': False,
                'writes_executed': False,
                'write_verification': False,
                'rollback_executed': False,
                'final_state_preserved': True,
                'runtime_write_boundary': True,
                'write_boundary_reason': 'Verified bridge exposes discovery only; scalar/property write and rollback endpoints are absent from the current runtime capability surface.',
            },
            'verified': True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print('Stage 5D.44 transform scalar no-op roundtrip capability boundary passed.')
        return 0
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': type(exc).__name__ + ': ' + str(exc), 'verified': False}, indent=2, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
