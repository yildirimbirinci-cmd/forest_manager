/*
    Forest Manager - 3ds Max 2020 Bridge
    Stage 1: PING and GET_SELECTION

    Protocol:
      TCP localhost:49491
      One ASCII command per connection, newline terminated.
      One UTF-8 JSON response per connection, newline terminated.

    The listener is polled by a MAXScript timer so all scene inspection
    remains on the 3ds Max main thread.
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

    fn jsonString value =
    (
        "\"" + (jsonEscape value) + "\""
    ),

    fn boolJson value =
    (
        if value then "true" else "false"
    ),

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
        ",\"bridge_version\":\"0.1.0\"}"
    ),

    fn getSelectionJson =
    (
        if selection.count != 1 then
        (
            throw "Select exactly one object in 3ds Max."
        )

        local obj = selection[1]
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

        "{\"name\":" + (jsonString objName) +
        ",\"class\":" + (jsonString objClass) +
        ",\"super_class\":" + (jsonString objSuperClass) +
        ",\"is_shape\":" + (boolJson isShape) +
        ",\"is_spline\":" + (boolJson isSpline) +
        ",\"spline_count\":" + (splineCount as string) +
        ",\"all_closed\":" + (boolJson allClosed) + "}"
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
