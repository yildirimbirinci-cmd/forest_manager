/*
    Forest Manager bridge startup shim.

    This file is copied next to ForestManager_Bridge.ms in the 3ds Max user
    scripts/startup directory. 3ds Max executes startup scripts automatically,
    so the current project bridge is loaded again after Windows/3ds Max restart.

    The shim never edits scene objects. It only loads the adjacent bridge file.
*/

fn fmForestManagerStartBridge =
(
    local thisFile = ""
    local thisDir = ""
    local bridgeFile = ""

    try (thisFile = getSourceFileName()) catch()
    if thisFile == undefined or thisFile == "" then
    (
        format "Forest Manager AutoStart: source file path is unavailable.\n"
        return false
    )

    thisDir = getFilenamePath thisFile
    bridgeFile = pathConfig.appendPath thisDir "ForestManager_Bridge.ms"

    if not (doesFileExist bridgeFile) then
    (
        format "Forest Manager AutoStart: bridge file was not found: %\n" bridgeFile
        return false
    )

    try
    (
        fileIn bridgeFile quiet:true
        format "Forest Manager AutoStart: bridge loaded from %\n" bridgeFile
        true
    )
    catch
    (
        format "Forest Manager AutoStart: bridge load failed: %\n" (getCurrentException())
        false
    )
)

fmForestManagerStartBridge()
