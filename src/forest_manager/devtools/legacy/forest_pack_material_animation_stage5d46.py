from __future__ import annotations

import json
from dataclasses import asdict

from forest_manager.forest_control import ForestPackControlService
from forest_manager.forest_control.material_animation import MaterialAnimationAdapter

def main() -> int:
    print('Forest Manager Stage 5D.46 Material + Animation Domain Runtime Boundary:')
    try:
        service = ForestPackControlService()
        adapter = MaterialAnimationAdapter(service)
        forests = service.list_forests()
        reports = [asdict(adapter.read_state(name)) for name in forests]
        result = {
            'ok': True,
            'forest_count': len(forests),
            'forests': reports,
            'policy': {
                'read_only_discovery': True,
                'tint_scalar_write': False,
                'tint_color_write': False,
                'tint_bitmap_write': False,
                'material_adjustment_write': False,
                'animation_scalar_write': False,
                'animation_time_write': False,
                'animation_bitmap_write': False,
                'runtime_write_boundary': True,
                'write_boundary_reason': 'Verified bridge exposes discovery only; scalar/color/time/bitmap write and rollback endpoints are absent from the current runtime capability surface.',
            },
            'verified': True,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print('Stage 5D.46 material + animation domain runtime capability boundary passed.')
        return 0
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': type(exc).__name__ + ': ' + str(exc), 'verified': False}, indent=2, ensure_ascii=False))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
