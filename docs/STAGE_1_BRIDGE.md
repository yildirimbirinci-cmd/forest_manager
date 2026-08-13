# Stage 1 - 3ds Max Bridge

Target environment:

- 3ds Max 2020
- Forest Pack 9.4.0
- Forest Manager bridge port: `49491`
- Bind address: `127.0.0.1` only

## Purpose

This stage intentionally does not modify Forest Pack or the scene.

It proves two things:

1. Forest Manager can communicate with the running 3ds Max instance.
2. Forest Manager can inspect exactly one selected scene object and determine whether it is a spline/shape.

## Install and start the Max bridge

In 3ds Max 2020:

1. Open `Scripting > Run Script...`.
2. Run `maxscripts/ForestManager_Bridge.ms`.
3. The MAXScript Listener should report:
   `Forest Manager Bridge started on 127.0.0.1:49491`

The script uses a short UI timer to poll a localhost TCP listener. Scene inspection therefore happens from the 3ds Max main thread instead of a background worker.

## Python environment

Run Forest Manager with a normal external Python 3 environment. The external application is intentionally independent from 3ds Max 2020's Python runtime.

From the repository root, make the `src` directory importable for the smoke test.

PowerShell:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.bridge_smoke

## Acceptance test

### Test A - Connection

With 3ds Max running and the bridge script loaded:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.bridge_smoke

Expected first result:

    Bridge connected.

The returned data should identify Max year `2020`.

### Test B - Spline selection

1. Create a Line in 3ds Max.
2. Close the Line if it will be used as a Forest area.
3. Select only that Line.
4. Run the smoke command again.

Expected selection fields include:

- `is_shape: true`
- `is_spline: true`
- `spline_count: 1` for a simple one-spline Line
- `all_closed: true` when the spline is closed

### Negative tests

- Nothing selected: query must return a controlled error.
- More than one object selected: query must return a controlled error.
- Box selected: query should succeed but report `is_shape: false` and `is_spline: false`.

## Stop the bridge

In the MAXScript Listener:

    ForestManagerBridge.stop()

## Security boundary

Stage 1 listens only on `127.0.0.1`. It is not exposed to the LAN or internet.

No command in Stage 1 edits, creates, deletes, merges, saves, or exports scene content.
