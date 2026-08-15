# Stage 5D.13 - Visual Cluster Calibration

Basis:
The Stage 5D.12 viewport result confirmed that Forest Pack Clusters mode works,
but the planting pattern still contains too many small fragmented islands.

Target profile:
- Cluster Size: 30 m
- Roughness: 25%
- Blurry Edge: 20%
- Noise: 5%

The target is a Forest Manager visual-calibration policy derived from the
observed viewport result. It is not presented as an iToo default.

Usage:
- Preview: python -m forest_manager.app.cluster_visual_calibration_stage5d13
- Apply:   python -m forest_manager.app.cluster_visual_calibration_stage5d13 --apply

The 30 m target is converted at runtime using the active 3ds Max scene unit
configuration via `units.decodeValue "1m"`. No fixed centimeters/meters system
unit assumption is used.

Protected:
- divers remains 2
- density
- geometry probabilities
- scale variation
- rotation
- translation

If post-apply verification fails, previous cluster and protected values are
restored.

Bridge version: 0.9.26
