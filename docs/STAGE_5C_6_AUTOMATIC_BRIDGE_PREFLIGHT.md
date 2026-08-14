# Stage 5C.6 - Automatic Bridge Preflight

Goal: normal VS Code runtime/test commands must no longer require a separate bridge reload command.

A shared runtime bridge helper now performs this preflight before unit-sensitive commands:

1. PING the currently running bridge.
2. If its version already matches the project bridge, continue immediately.
3. Otherwise request RELOAD_BRIDGE with the current project `maxscripts/ForestManager_Bridge.ms` path.
4. Wait for the old listener/timer to stop and the new script to load.
5. PING repeatedly until the expected bridge version is active.
6. Only then execute the requested command.

Integrated commands in this stage:

- `python -m forest_manager.app.density_stage5c3`
- `python -m forest_manager.app.scene_units_stage5c4`
- `python -m forest_manager.app.reload_bridge` remains available as an explicit diagnostic/preflight command.

Density behavior is unchanged: its default user-facing request remains exactly 75.0 meters.

Bridge version: 0.9.14
