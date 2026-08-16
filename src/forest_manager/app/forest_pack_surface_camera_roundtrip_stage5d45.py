from __future__ import annotations

import json

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.surface_camera import SurfaceCameraAdapter


def main() -> int:
    print('Forest Manager Stage 5D.45 Surface + Camera Scalar No-op Roundtrip Boundary:')
    try:
        service = ForestPackControlService()
        adapter = SurfaceCameraAdapter(service)
        forests = service.list_forests()
        reports = []
        for forest_name in forests:
            before = adapter.scalar_snapshot(forest_name)
            plan = adapter.no_op_scalar_plan(forest_name)
            preserved = before == plan
            if not preserved:
                raise RuntimeError('No-op surface/camera plan changed state: ' + forest_name)
            reports.append({
                'forest_name': forest_name,
                'plan_preserved': preserved,
                'write_executed': False,
                'rollback_executed': False,
                'altitude': [before.get('altmin'), before.get('altmax')],
                'slope': [before.get('slopemin'), before.get('slopemax')],
                'uv_multiplier': [before.get('uvmultscalex'), before.get('uvmultscaley')],
                'camera_limit': before.get('camlimit'),
                'camera_lod': before.get('camlod'),
                'camera_range': [before.get('camnear'), before.get('camfar')],
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
                'surface_list_write': False,
                'surface_link_write': False,
                'camera_reference_write': False,
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
        print('Stage 5D.45 surface + camera scalar no-op roundtrip capability boundary passed.')
        return 0
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': type(exc).__name__ + ': ' + str(exc), 'verified': False}, indent=2, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
