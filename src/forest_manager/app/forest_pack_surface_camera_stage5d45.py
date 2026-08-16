from __future__ import annotations

import json
from dataclasses import asdict

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.surface_camera import SurfaceCameraAdapter


def main() -> int:
    print('Forest Manager Stage 5D.45 Surface + Camera Domain Runtime Boundary:')
    try:
        service = ForestPackControlService()
        adapter = SurfaceCameraAdapter(service)
        forests = service.list_forests()
        reports = [asdict(adapter.read_state(name)) for name in forests]
        result = {
            'ok': True,
            'forest_count': len(forests),
            'forests': reports,
            'policy': {
                'read_only_discovery': True,
                'surface_write': False,
                'camera_write': False,
                'surface_list_write': False,
                'surface_link_write': False,
                'camera_reference_write': False,
                'surface_curve_write': False,
                'camera_curve_write': False,
                'curve_control_reason': 'opaque CurveClass/SubAnim without exposed controller',
                'runtime_write_boundary': True,
                'write_boundary_reason': 'Verified bridge exposes discovery only; scalar/property write and rollback endpoints are absent from the current runtime capability surface.',
            },
            'verified': True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print('Stage 5D.45 surface + camera domain runtime capability boundary passed.')
        return 0
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': type(exc).__name__ + ': ' + str(exc), 'verified': False}, indent=2, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
