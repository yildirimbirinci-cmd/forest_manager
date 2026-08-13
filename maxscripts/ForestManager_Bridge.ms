/*
    Forest Manager - 3ds Max 2020 Bridge
    Stage 2: PING, selection inspection, Forest Pack detection,
             and verified Forest creation from one closed spline.

    Target:
      3ds Max 2020
      Forest Pack 9.4.0

    Security:
      TCP bind is localhost only.
      Stage 2 scene mutation is limited to CREATE_FOREST_FROM_SELECTION.
*/

global ForestManagerBridge

struct ForestManagerBridgeState
(
    listener,
    pollTimer,
    host = "127.0.0.1",
    port = 49491,
    running = false,

    fn jsonEscape value =
    (
        local s = value as string
        s = substituteString s "\\" "\\\\"
        s = substituteString s "\"" "\\\""
        s = substituteString s "\r" "\\r"
        s = substituteString s "\n" "\\n"
        s = substituteString s "\t" "\\t"
        s
    ),

    fn jsonString value = ("\"" + (jsonEscape value) + "\""),
    fn boolJson value = (if value then "true" else "false"),

    fn makeError command message =
    (
        "{\"ok\":false,\"command\":" + (jsonString command) +
        ",\"data\":{},\"error\":" + (jsonString message) + "}"
    ),

    fn getMaxVersionJson =
    (
        local mv = maxVersion()
        local maxYear = if mv.count >= 8 then mv[8] else 0
        "{\"max_year\":" + (maxYear as string) +
        ",\"max_version\":" + (jsonString (mv as string)) +
        ",\"bridge_version\":\"0.2.0\"}"
    ),

    fn getSingleSelection =
    (
        if selection.count != 1 do
            throw "Select exactly one object in 3ds Max."
        selection[1]
    ),

    fn getSelectionData obj =
    (
        local objName = obj.name as string
        local objClass = (classOf obj) as string
        local objSuperClass = (superClassOf obj) as string
        local isShape = (superClassOf obj == Shape)
        local isSpline = false
        local splineCount = 0
        local allClosed = false

        if isShape then
        (
            try
            (
                splineCount = numSplines obj
                isSpline = splineCount > 0

                if splineCount > 0 then
                (
                    allClosed = true
                    for splineIndex = 1 to splineCount while allClosed do
                    (
                        if not (isClosed obj splineIndex) do allClosed = false
                    )
                )
            )
            catch
            (
                splineCount = 0
                isSpline = false
                allClosed = false
            )
        )

        #(
            objName,
            objClass,
            objSuperClass,
            isShape,
            isSpline,
            splineCount,
            allClosed
        )
    ),

    fn getSelectionJson =
    (
        local obj = getSingleSelection()
        local d = getSelectionData obj

        "{\"name\":" + (jsonString d[1]) +
        ",\"class\":" + (jsonString d[2]) +
        ",\"super_class\":" + (jsonString d[3]) +
        ",\"is_shape\":" + (boolJson d[4]) +
        ",\"is_spline\":" + (boolJson d[5]) +
        ",\"spline_count\":" + (d[6] as string) +
        ",\"all_closed\":" + (boolJson d[7]) + "}"
    ),

    fn forestPackAvailable =
    (
        local available = false
        try
        (
            available = (::Forest_Pro != undefined)
        )
        catch
        (
            available = false
        )
        available
    ),

    fn getForestPackInfoJson =
    (
        local available = forestPackAvailable()
        local className = ""
        local forestCount = 0

        if available then
        (
            className = "::Forest_Pro"
            for obj in objects do
            (
                try
                (
                    if isKindOf obj ::Forest_Pro do forestCount += 1
                )
                catch()
            )
        )

        "{\"available\":" + (boolJson available) +
        ",\"class_name\":" + (jsonString className) +
        ",\"forest_count\":" + (forestCount as string) + "}"
    ),

    fn requireArrayProperty forestNode propName =
    (
        if not (isProperty forestNode propName) do
            throw ("Forest Pack property missing: " + (propName as string))
        local value = getProperty forestNode propName
        if classOf value != ArrayParameter do
            throw ("Forest Pack property is not an ArrayParameter: " + (propName as string))
        value
    ),

    fn resizeAreaArrays forestNode newCount =
    (
        local props = #(
            #aridlist,
            #pf_aractivelist,
            #arnamelist,
            #arnodelist,
            #arnodenamelist,
            #artypelist,
            #arincexclist,
            #arresollist,
            #arslicelist,
            #arslicetoplist,
            #arwidthlist,
            #armaplist,
            #arscalelist,
            #arthresholdlist,
            #arselspeclist,
            #arspeclist,
            #arpaintlist,
            #arflafdenslist,
            #arflafscalist,
            #arflinvlist,
            #arboundchecklist,
            #arshapelist,
            #arobscalelist,
            #arsurfidlist,
            #arzoffset
        )

        for propName in props do
        (
            local arr = requireArrayProperty forestNode propName
            arr.count = newCount
        )
        true
    ),

    fn makeForestName =
    (
        local index = 1
        local candidate = ""
        while true do
        (
            candidate = "FM_Forest_" + (formattedPrint index format:"03d")
            if getNodeByName candidate == undefined do return candidate
            index += 1
        )
    ),

    fn addSplineIncludeArea forestNode splineNode =
    (
        local currentCount = forestNode.aridlist.count
        local index = currentCount + 1

        resizeAreaArrays forestNode index

        forestNode.aridlist[index] = index
        forestNode.pf_aractivelist[index] = true
        forestNode.arnamelist[index] = splineNode.name
        forestNode.arnodelist[index] = splineNode
        forestNode.arnodenamelist[index] = splineNode.name

        -- 0 = spline area; 0 = Include. These are the normal values used by
        -- Forest Pack's array-backed Area list.
        forestNode.artypelist[index] = 0
        forestNode.arincexclist[index] = 0
        forestNode.arobscalelist[index] = 100

        index
    ),

    fn verifySplineArea forestNode splineNode areaIndex =
    (
        if forestNode == undefined then return false
        if splineNode == undefined then return false
        if areaIndex < 1 then return false
        if forestNode.aridlist.count < areaIndex then return false
        if forestNode.arnodelist[areaIndex] != splineNode then return false
        if forestNode.arincexclist[areaIndex] != 0 then return false
        true
    ),

    fn createForestFromSelectionJson =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        local splineNode = getSingleSelection()
        local selectionData = getSelectionData splineNode

        if not selectionData[5] do
            throw "Selected object is not a spline."
        if not selectionData[7] do
            throw "Selected spline must be closed for Stage 2."

        local forestNode = undefined
        local areaIndex = 0

        try
        (
            forestNode = ::Forest_Pro()
            forestNode.name = makeForestName()
            areaIndex = addSplineIncludeArea forestNode splineNode

            if not (verifySplineArea forestNode splineNode areaIndex) do
                throw "Forest spline-area verification failed after creation."

            completeRedraw()

            "{\"forest_name\":" + (jsonString forestNode.name) +
            ",\"forest_class\":" + (jsonString ((classOf forestNode) as string)) +
            ",\"area_count\":" + (forestNode.aridlist.count as string) +
            ",\"area_index\":" + (areaIndex as string) +
            ",\"area_name\":" + (jsonString forestNode.arnamelist[areaIndex]) +
            ",\"area_node\":" + (jsonString splineNode.name) +
            ",\"include\":true" +
            ",\"verified\":true}"
        )
        catch
        (
            local message = getCurrentException()
            try
            (
                if forestNode != undefined do delete forestNode
            )
            catch()
            format "Forest Manager Stage 2 creation error: %\n" message
            throw
        )
    ),

    fn handleCommand rawCommand =
    (
        local command = toUpper (trimLeft (trimRight rawCommand))

        case command of
        (
            "PING":
            (
                "{\"ok\":true,\"command\":\"PING\",\"data\":" +
                getMaxVersionJson() + ",\"error\":\"\"}"
            )

            "GET_SELECTION":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"GET_SELECTION\",\"data\":" +
                    getSelectionJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "GET_SELECTION" (getCurrentException())
                )
            )

            "GET_FORESTPACK_INFO":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"GET_FORESTPACK_INFO\",\"data\":" +
                    getForestPackInfoJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "GET_FORESTPACK_INFO" (getCurrentException())
                )
            )

            "CREATE_FOREST_FROM_SELECTION":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"CREATE_FOREST_FROM_SELECTION\",\"data\":" +
                    createForestFromSelectionJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "CREATE_FOREST_FROM_SELECTION" (getCurrentException())
                )
            )

            default:
            (
                makeError command "Unknown command."
            )
        )
    ),

    fn processPending =
    (
        if listener == undefined then return false
        if not listener.Pending() then return false

        local client = undefined
        local stream = undefined
        local reader = undefined
        local writer = undefined

        try
        (
            client = listener.AcceptTcpClient()
            stream = client.GetStream()
            reader = dotNetObject "System.IO.StreamReader" stream (dotNetObject "System.Text.UTF8Encoding" false)
            writer = dotNetObject "System.IO.StreamWriter" stream (dotNetObject "System.Text.UTF8Encoding" false)
            writer.AutoFlush = true

            local command = reader.ReadLine()
            local response = if command == undefined then
                makeError "" "Empty command."
            else
                handleCommand command

            writer.WriteLine response
        )
        catch
        (
            format "Forest Manager Bridge request error: %\n" (getCurrentException())
        )

        try (if writer != undefined do writer.Close()) catch()
        try (if reader != undefined do reader.Close()) catch()
        try (if stream != undefined do stream.Close()) catch()
        try (if client != undefined do client.Close()) catch()

        true
    ),

    fn start =
    (
        if running do
        (
            format "Forest Manager Bridge is already running on 127.0.0.1:%\n" port
            return true
        )

        try
        (
            local ipAddressClass = dotNetClass "System.Net.IPAddress"
            local tcpListenerClass = dotNetClass "System.Net.Sockets.TcpListener"
            listener = dotNetObject tcpListenerClass ipAddressClass.Loopback port
            listener.Start()

            pollTimer = dotNetObject "System.Windows.Forms.Timer"
            pollTimer.Interval = 100
            dotNet.addEventHandler pollTimer "Tick" (fn onForestManagerBridgeTick sender args = (
                if ForestManagerBridge != undefined do
                (
                    try
                    (
                        while ForestManagerBridge.listener.Pending() do
                        (
                            ForestManagerBridge.processPending()
                        )
                    )
                    catch
                    (
                        format "Forest Manager Bridge poll error: %\n" (getCurrentException())
                    )
                )
            ))
            pollTimer.Start()

            running = true
            format "Forest Manager Bridge started on 127.0.0.1:%\n" port
            true
        )
        catch
        (
            format "Forest Manager Bridge start failed: %\n" (getCurrentException())
            stop()
            false
        )
    ),

    fn stop =
    (
        try
        (
            if pollTimer != undefined do
            (
                pollTimer.Stop()
                pollTimer.Dispose()
            )
        )
        catch()

        try
        (
            if listener != undefined do listener.Stop()
        )
        catch()

        pollTimer = undefined
        listener = undefined
        running = false
        format "Forest Manager Bridge stopped.\n"
        true
    )
)

try
(
    if ForestManagerBridge != undefined do ForestManagerBridge.stop()
)
catch()

ForestManagerBridge = ForestManagerBridgeState()
ForestManagerBridge.start()
