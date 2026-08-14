# Stage 5C.5 - Automatic Bridge Reload

The running 3ds Max bridge can now reload the current project copy of
`maxscripts/ForestManager_Bridge.ms` without manually stopping the old bridge.

Bootstrap rule:
- Bridge 0.9.13 must be run manually in 3ds Max once, because older bridges do
  not know the RELOAD_BRIDGE command.
- After that, use:

    python -m forest_manager.app.reload_bridge

The command asks the current bridge to defer a reload, returns the TCP response,
stops/disposes the old timer/listener through the normal bridge bootstrap, loads
the new script with fileIn, and verifies the new bridge with PING.

The reload path is base64 encoded over the localhost protocol.

Bridge version: 0.9.13
