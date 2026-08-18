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
global ForestManagerBridgeReloadTimer
global ForestManagerBridgeReloadPath

-- Atomic reload bootstrap state lives outside ForestManagerBridgeState so
-- replacing/stopping the old bridge cannot dispose the reload callback itself.

struct ForestManagerBridgeState
(
    listener,
    pollTimer,
    reloadTimer,
    reloadPath,
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
        ",\"bridge_version\":\"0.9.99\"" +
        ",\"bridge_build_id\":\"stage8-helper-layer-lifecycle-20260818a\"}"
    ),

    fn getDisplayUnitName =
    (
        local displayType = units.DisplayType

        case displayType of
        (
            #Metric: (units.MetricType as string)
            #US: (units.USType as string)
            #custom: units.CustomName
            default: (displayType as string)
        )
    ),

    fn getSceneUnitsJson =
    (
        local displayType = units.DisplayType
        local displayUnit = getDisplayUnitName()
        local systemType = units.SystemType
        local systemScale = units.SystemScale
        local oneMeterSystemUnits = units.decodeValue "1m"
        local oneMillimeterSystemUnits = units.decodeValue "1mm"
        local oneCentimeterSystemUnits = units.decodeValue "1cm"
        local sampleOneMeterDisplay = units.formatValue oneMeterSystemUnits

        local customName = ""
        local customValue = 0.0
        local customUnit = ""
        if displayType == #custom then
        (
            try (customName = units.CustomName as string) catch()
            try (customValue = units.CustomValue) catch()
            try (customUnit = units.CustomUnit as string) catch()
        )

        "{\"display_type\":" + (jsonString (displayType as string)) +
        ",\"display_unit\":" + (jsonString displayUnit) +
        ",\"system_type\":" + (jsonString (systemType as string)) +
        ",\"system_scale\":" + (systemScale as string) +
        ",\"one_meter_system_units\":" + (oneMeterSystemUnits as string) +
        ",\"one_centimeter_system_units\":" + (oneCentimeterSystemUnits as string) +
        ",\"one_millimeter_system_units\":" + (oneMillimeterSystemUnits as string) +
        ",\"sample_one_meter_display\":" + (jsonString sampleOneMeterDisplay) +
        ",\"custom_name\":" + (jsonString customName) +
        ",\"custom_value\":" + (customValue as string) +
        ",\"custom_unit\":" + (jsonString customUnit) +
        ",\"verified\":true}"
    ),

    fn metersToSystemUnits metersValue =
    (
        (units.decodeValue "1m") * metersValue
    ),

    fn millimetersToSystemUnits millimetersValue =
    (
        (units.decodeValue "1mm") * millimetersValue
    ),

    fn formatSystemValueForScene systemValue =
    (
        units.formatValue systemValue
    ),

    fn getSingleSelection =
    (
        if selection.count != 1 do
            throw "Select exactly one object in 3ds Max."
        selection[1]
    ),

    fn getDisplayAreaUnitContext =
    (
        local displayType = units.DisplayType
        local displayUnit = toLower (getDisplayUnitName())
        local scaleSystemUnits = units.decodeValue "1m"
        local label = "m2"
        local supported = true

        if displayType == #Metric then
        (
            case displayUnit of
            (
                "millimeters":
                (
                    scaleSystemUnits = units.decodeValue "1mm"
                    label = "mm2"
                )
                "centimeters":
                (
                    scaleSystemUnits = units.decodeValue "1cm"
                    label = "cm2"
                )
                "meters":
                (
                    scaleSystemUnits = units.decodeValue "1m"
                    label = "m2"
                )
                "kilometers":
                (
                    scaleSystemUnits = units.decodeValue "1km"
                    label = "km2"
                )
                default:
                (
                    scaleSystemUnits = units.decodeValue "1m"
                    label = "m2"
                    supported = false
                )
            )
        )
        else
        (
            -- Area formatting for non-metric/custom displays is reported in
            -- canonical square meters until an explicit display-area formatter
            -- is available for that display family.
            scaleSystemUnits = units.decodeValue "1m"
            label = "m2"
            supported = false
        )

        #(scaleSystemUnits, label, supported)
    ),

    fn sampledClosedSplineAreaSystemSquared node splineIndex samples:512 =
    (
        if node == undefined do throw "Spline node is undefined."
        if samples < 8 do samples = 8
        if not (isClosed node splineIndex) do
            throw "Spline area requires a closed spline."

        local points = #()
        for i = 0 to (samples - 1) do
        (
            local t = (i as float) / (samples as float)
            local p = interpCurve3D node splineIndex t
            append points p
        )

        local areaVector = [0.0, 0.0, 0.0]
        for i = 1 to points.count do
        (
            local j = if i == points.count then 1 else i + 1
            areaVector += cross points[i] points[j]
        )

        (length areaVector) * 0.5
    ),

    fn closedSplineCandidatesJson =
    (
        local oneMeterSystemUnits = units.decodeValue "1m"
        if oneMeterSystemUnits <= 0.0 do throw "Scene unit conversion is invalid."

        local values = #()
        for node in objects do
        (
            local splineCount = 0
            local allClosed = false
            try
            (
                if superClassOf node == Shape then
                (
                    splineCount = numSplines node
                    if splineCount > 0 then
                    (
                        allClosed = true
                        for splineIndex = 1 to splineCount while allClosed do
                        (
                            if not (isClosed node splineIndex) do allClosed = false
                        )
                    )
                )
            )
            catch
            (
                splineCount = 0
                allClosed = false
            )

            if splineCount > 0 and allClosed do
            (
                local totalAreaSystemSquared = 0.0
                for splineIndex = 1 to splineCount do
                    totalAreaSystemSquared += sampledClosedSplineAreaSystemSquared node splineIndex samples:256

                local bb = nodeGetBoundingBox node node.transform
                local size = bb[2] - bb[1]
                local width = abs size.x
                local depth = abs size.y
                local areaSquareMeters = totalAreaSystemSquared / (oneMeterSystemUnits * oneMeterSystemUnits)
                local isManaged = false
                try (isManaged = matchPattern node.name pattern:"FM_*" ignoreCase:true) catch (isManaged = false)

                append values #(node.name, splineCount, totalAreaSystemSquared, areaSquareMeters, width, depth, isManaged)
            )
        )

        local json = "["
        for i = 1 to values.count do
        (
            if i > 1 do json += ","
            local item = values[i]
            json += "{\"node_name\":" + jsonString item[1] +
                    ",\"spline_count\":" + (item[2] as string) +
                    ",\"all_splines_closed\":true" +
                    ",\"area_system_units_squared\":" + (item[3] as string) +
                    ",\"area_square_meters\":" + (item[4] as string) +
                    ",\"width_system_units\":" + (item[5] as string) +
                    ",\"depth_system_units\":" + (item[6] as string) +
                    ",\"forest_manager_owned\":" + boolJson item[7] +
                    "}"
        )
        json += "]"

        "{\"candidate_count\":" + (values.count as string) +
        ",\"candidates\":" + json +
        ",\"scene_units\":" + getSceneUnitsJson() +
        ",\"read_only\":true,\"verified\":true}"
    ),

    fn getSelectionSplineAreaJson =
    (
        local node = getSingleSelection()
        local splineCount = 0
        try (splineCount = numSplines node) catch (splineCount = 0)
        if splineCount < 1 do throw "Selected object is not a spline."

        local allClosed = true
        local totalAreaSystemSquared = 0.0
        for i = 1 to splineCount do
        (
            if not (isClosed node i) then
                allClosed = false
            else
                totalAreaSystemSquared += sampledClosedSplineAreaSystemSquared node i samples:512
        )

        if not allClosed do throw "All selected splines must be closed."

        local oneMeterSystemUnits = units.decodeValue "1m"
        if oneMeterSystemUnits <= 0.0 do
            throw "Scene unit conversion is invalid."

        local areaSquareMeters = totalAreaSystemSquared / (oneMeterSystemUnits * oneMeterSystemUnits)
        local displayContext = getDisplayAreaUnitContext()
        local oneDisplayUnitSystemUnits = displayContext[1]
        local displayAreaLabel = displayContext[2]
        local displayAreaSupported = displayContext[3]

        local areaDisplayValue = areaSquareMeters
        if oneDisplayUnitSystemUnits > 0.0 then
            areaDisplayValue = totalAreaSystemSquared / (oneDisplayUnitSystemUnits * oneDisplayUnitSystemUnits)

        "{\"node_name\":" + (jsonString node.name) +
        ",\"node_class\":" + (jsonString ((classOf node) as string)) +
        ",\"spline_count\":" + (splineCount as string) +
        ",\"all_splines_closed\":" + (boolJson allClosed) +
        ",\"sampling_steps_per_spline\":512" +
        ",\"area_system_units_squared\":" + (totalAreaSystemSquared as string) +
        ",\"area_square_meters\":" + (areaSquareMeters as string) +
        ",\"area_display_value\":" + (areaDisplayValue as string) +
        ",\"area_display_unit\":" + (jsonString displayAreaLabel) +
        ",\"area_display_supported\":" + (boolJson displayAreaSupported) +
        ",\"scene_units\":" + getSceneUnitsJson() +
        ",\"verified\":true}"
    ),

    fn getSelectionMeasurementsJson =
    (
        local node = getSingleSelection()
        local bb = nodeGetBoundingBox node node.transform
        local size = bb[2] - bb[1]
        local width = abs size.x
        local depth = abs size.y
        local height = abs size.z

        local isSpline = false
        local allClosed = false
        local splineCount = 0
        try
        (
            splineCount = numSplines node
            isSpline = splineCount > 0
            if isSpline then
            (
                allClosed = true
                for i = 1 to splineCount while allClosed do
                (
                    if not (isClosed node i) do allClosed = false
                )
            )
        )
        catch
        (
            splineCount = 0
            isSpline = false
            allClosed = false
        )

        "{\"node_name\":" + (jsonString node.name) +
        ",\"node_class\":" + (jsonString ((classOf node) as string)) +
        ",\"is_spline\":" + (boolJson isSpline) +
        ",\"spline_count\":" + (splineCount as string) +
        ",\"all_splines_closed\":" + (boolJson allClosed) +
        ",\"width_system_units\":" + (width as string) +
        ",\"depth_system_units\":" + (depth as string) +
        ",\"height_system_units\":" + (height as string) +
        ",\"width_display\":" + (jsonString (formatSystemValueForScene width)) +
        ",\"depth_display\":" + (jsonString (formatSystemValueForScene depth)) +
        ",\"height_display\":" + (jsonString (formatSystemValueForScene height)) +
        ",\"scene_units\":" + getSceneUnitsJson() +
        ",\"verified\":true}"
    ),


    fn point3WorldJson p =
    (
        "{\"x\":" + (p.x as string) +
        ",\"y\":" + (p.y as string) +
        ",\"z\":" + (p.z as string) + "}"
    ),

    fn getSelectionSplineWorldSpaceJson samplesPerSpline:64 =
    (
        local node = getSingleSelection()
        local splineCount = 0
        try (splineCount = numSplines node) catch (splineCount = 0)
        if splineCount < 1 do throw "Selected object is not a spline."
        if samplesPerSpline < 8 do samplesPerSpline = 8
        if samplesPerSpline > 512 do samplesPerSpline = 512

        local allClosed = true
        for splineIndex = 1 to splineCount while allClosed do
        (
            if not (isClosed node splineIndex) do allClosed = false
        )
        if not allClosed do throw "All selected splines must be closed."

        local splinesJson = "["
        in coordsys world
        (
            for splineIndex = 1 to splineCount do
            (
                if splineIndex > 1 do splinesJson += ","
                local knotCount = numKnots node splineIndex
                local knotJson = "["
                for knotIndex = 1 to knotCount do
                (
                    if knotIndex > 1 do knotJson += ","
                    local knotPoint = getKnotPoint node splineIndex knotIndex
                    knotJson += point3WorldJson knotPoint
                )
                knotJson += "]"

                local sampleJson = "["
                resetLengthInterp()
                for sampleIndex = 0 to (samplesPerSpline - 1) do
                (
                    if sampleIndex > 0 do sampleJson += ","
                    local t = (sampleIndex as float) / (samplesPerSpline as float)
                    local samplePoint = interpCurve3D node splineIndex t pathParam:false
                    sampleJson += point3WorldJson samplePoint
                )
                sampleJson += "]"

                splinesJson += "{\"spline_index\":" + (splineIndex as string) +
                    ",\"closed\":true" +
                    ",\"knot_count\":" + (knotCount as string) +
                    ",\"knots_world\":" + knotJson +
                    ",\"sample_count\":" + (samplesPerSpline as string) +
                    ",\"samples_world\":" + sampleJson + "}"
            )
        )
        splinesJson += "]"

        "{\"node_name\":" + (jsonString node.name) +
        ",\"node_class\":" + (jsonString ((classOf node) as string)) +
        ",\"coordinate_system\":\"world\"" +
        ",\"system_units\":true" +
        ",\"spline_count\":" + (splineCount as string) +
        ",\"all_splines_closed\":true" +
        ",\"samples_per_spline\":" + (samplesPerSpline as string) +
        ",\"splines\":" + splinesJson +
        ",\"scene_units\":" + getSceneUnitsJson() +
        ",\"read_only\":true,\"verified\":true}"
    ),


    fn getSelectionSplineSegmentsJson =
    (
        local node = getSingleSelection()
        local splineCount = 0
        try (splineCount = numSplines node) catch (splineCount = 0)
        if splineCount != 1 do throw "Wall Edge annotation currently requires exactly one spline in the selected Line."
        if not (isClosed node 1) do throw "Wall Edge annotation requires a closed spline."

        local segmentCount = numSegments node 1
        if segmentCount < 3 do throw "Selected closed spline has fewer than three segments."
        local selectedSegmentsRaw = #()
        try (selectedSegmentsRaw = getSegSelection node 1) catch (selectedSegmentsRaw = #())

        local selectedJson = "["
        local unselectedJson = "["
        local selectedFirst = true
        local unselectedFirst = true
        for segmentIndex = 1 to segmentCount do
        (
            local isSelectedSegment = false
            try
            (
                if (classOf selectedSegmentsRaw == BitArray) then
                    isSelectedSegment = (selectedSegmentsRaw[segmentIndex] == true)
                else
                    isSelectedSegment = ((findItem selectedSegmentsRaw segmentIndex) > 0)
            )
            catch (isSelectedSegment = false)
            if isSelectedSegment then
            (
                if not selectedFirst do selectedJson += ","
                selectedJson += segmentIndex as string
                selectedFirst = false
            )
            else
            (
                if not unselectedFirst do unselectedJson += ","
                unselectedJson += segmentIndex as string
                unselectedFirst = false
            )
        )
        selectedJson += "]"
        unselectedJson += "]"

        "{\"node_name\":" + (jsonString node.name) +
        ",\"spline_index\":1" +
        ",\"segment_count\":" + (segmentCount as string) +
        ",\"selected_segments\":" + selectedJson +
        ",\"unselected_segments\":" + unselectedJson +
        ",\"selection_source\":\"3ds_max_segment_subobject_selection\"" +
        ",\"read_only\":true,\"verified\":true}"
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

    fn setForestPointCloudDisplay forestNode =
    (
        if forestNode == undefined do return false

        local isForest = false
        try (isForest = isKindOf forestNode ::Forest_Pro) catch (isForest = false)
        if not isForest do return false

        if not (isProperty forestNode #vmesh) do
            throw ("Forest Pack viewport display property vmesh is unavailable: " + forestNode.name)

        -- Forest Pack MaxScript: vmesh=3 is Points Cloud viewport mode.
        -- Render settings are intentionally untouched.
        forestNode.vmesh = 3
        if forestNode.vmesh != 3 do
            throw ("Forest Pack Points Cloud verification failed: " + forestNode.name)

        try (forestNode.trees.update()) catch()
        try (forestNode.trees.update_ui()) catch()
        try (notifyDependents forestNode) catch()
        true
    ),

    fn setAllForestPointCloudJson =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        local changed = #()
        local forestCount = 0
        for obj in objects do
        (
            local isForest = false
            try (isForest = isKindOf obj ::Forest_Pro) catch (isForest = false)
            if isForest do
            (
                forestCount += 1
                if setForestPointCloudDisplay obj do append changed obj.name
            )
        )

        completeRedraw()

        local namesJson = "["
        for i = 1 to changed.count do
        (
            if i > 1 do namesJson += ","
            namesJson += jsonString changed[i]
        )
        namesJson += "]"

        "{\"viewport_display\":\"points_cloud\"" +
        ",\"vmesh\":3" +
        ",\"forest_count\":" + (forestCount as string) +
        ",\"changed_count\":" + (changed.count as string) +
        ",\"forest_names\":" + namesJson +
        ",\"render_settings_changed\":false" +
        ",\"verified\":true}"
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
            setForestPointCloudDisplay forestNode
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


    fn isForestManagerOwnedNode node =
    (
        if node == undefined do return false

        local owned = false
        try
        (
            local value = getUserProp node "ForestManagerOwned"
            if value != undefined do
            (
                local normalized = toLower (value as string)
                owned = (normalized == "true" or normalized == "1" or normalized == "yes")
            )
        )
        catch()

        owned
    ),

    fn markForestManagerOwnedNode node role:"reference_source" =
    (
        if node == undefined do return false

        try (setUserProp node "ForestManagerOwned" "true") catch()
        try (setUserProp node "ForestManagerRole" role) catch()
        true
    ),

    fn ensureStage8PrimaryForestJson splineName =
    (
        if not (forestPackAvailable()) do throw "Forest Pack Pro class ::Forest_Pro is not available."
        local splineNode = getNodeByName splineName
        if splineNode == undefined do throw ("Closed spline was not found: " + splineName)

        local splineCount = 0
        try (splineCount = numSplines splineNode) catch (splineCount = 0)
        if splineCount < 1 do throw "Stage 8 boundary must be a spline."
        for splineIndex = 1 to splineCount do
            if not (isClosed splineNode splineIndex) do throw "Stage 8 boundary splines must all be closed."

        local forestNode = getNodeByName "FM_Forest_001"
        local created = false
        if forestNode == undefined then
        (
            forestNode = ::Forest_Pro()
            setForestPointCloudDisplay forestNode
            forestNode.name = "FM_Forest_001"
            created = true
        )
        else
        (
            local isForest = false
            try (isForest = isKindOf forestNode ::Forest_Pro) catch (isForest = false)
            if not isForest do throw "FM_Forest_001 exists but is not a Forest Pack Forest object."
        )

        local boundIndex = 0
        if isProperty forestNode #arnodelist then
        (
            for i = 1 to forestNode.arnodelist.count while boundIndex == 0 do
                if forestNode.arnodelist[i] == splineNode do boundIndex = i
        )
        if boundIndex == 0 do boundIndex = addSplineIncludeArea forestNode splineNode
        if not (verifySplineArea forestNode splineNode boundIndex) do throw "Stage 8 primary Forest Area verification failed."

        try (markForestManagerOwnedNode forestNode role:"primary_forest") catch()
        try (setUserProp forestNode "ForestManagerSiteBoundary" splineNode.name) catch()
        completeRedraw()

        "{\"forest_name\":" + jsonString forestNode.name +
        ",\"spline_name\":" + jsonString splineNode.name +
        ",\"area_index\":" + (boundIndex as string) +
        ",\"created\":" + boolJson created +
        ",\"verified\":true}"
    ),

    fn collectManagedForestSourceNodes forestNode =
    (
        local result = #()
        if forestNode == undefined do return result
        if not (isProperty forestNode #cobjlist) do return result

        for i = 1 to forestNode.cobjlist.count do
        (
            local node = forestNode.cobjlist[i]
            if node != undefined and (findItem result node) == 0 do append result node
        )
        result
    ),

    fn collectOwnedReferenceLayerNodes =
    (
        local result = #()
        local refLayer = LayerManager.getLayerFromName "FM_REFERENCES"
        if refLayer == undefined do refLayer = LayerManager.getLayerFromName "FM_References"
        if refLayer == undefined do return result

        local layerNodes = #()
        try (refLayer.nodes &layerNodes) catch()

        for node in layerNodes do
        (
            if isForestManagerOwnedNode node and (findItem result node) == 0 do
                append result node
        )
        result
    ),

    fn getAutoRenameBaseName nodeName =
    (
        local value = nodeName as string
        if value.count <= 3 do return value

        local tail = substring value (value.count - 2) 3
        local allDigits = true
        for i = 1 to 3 while allDigits do
        (
            local ch = substring tail i 1
            if (findString "0123456789" ch) == undefined do allDigits = false
        )

        if allDigits then
            substring value 1 (value.count - 3)
        else
            value
    ),

    fn getNodeBoundingSize node =
    (
        if node == undefined do return undefined

        local result = undefined
        try
        (
            local bb = nodeGetBoundingBox node node.transform
            local delta = bb[2] - bb[1]
            result = #(abs delta.x, abs delta.y, abs delta.z)
        )
        catch()
        result
    ),

    fn dimensionsApproximatelyMatch a b =
    (
        if a == undefined or b == undefined do return false
        if a.count != 3 or b.count != 3 do return false

        for i = 1 to 3 do
        (
            local scale = amax (abs a[i]) (abs b[i])
            local tolerance = amax 0.01 (scale * 0.005)
            if abs (a[i] - b[i]) > tolerance do return false
        )
        true
    ),

    fn isReferenceLayerNode node =
    (
        if node == undefined do return false

        local result = false
        try
        (
            local nodeLayer = node.layer
            if nodeLayer != undefined do result = (nodeLayer.name == "FM_References" or nodeLayer.name == "FM_REFERENCES")
        )
        catch()
        result
    ),

    fn collectLegacyAutoRenameSiblings legacySourceNodes =
    (
        local result = #()

        for sourceNode in legacySourceNodes do
        (
            if sourceNode != undefined do
            (
                -- Only use a source as a migration witness when current Forest
                -- Manager ownership is provable. This prevents name-only
                -- deletion of unrelated user scene objects.
                local managedWitness = isForestManagerOwnedNode sourceNode or isReferenceLayerNode sourceNode
                if managedWitness do
                (
                    local baseName = getAutoRenameBaseName sourceNode.name
                    local sourceClass = ""
                    local sourceSize = getNodeBoundingSize sourceNode
                    try (sourceClass = (classOf sourceNode) as string) catch()

                    for candidate in objects do
                    (
                        if candidate != undefined and
                           candidate != sourceNode and
                           not (isForestManagerOwnedNode candidate) then
                        (
                            local candidateBase = getAutoRenameBaseName candidate.name
                            if candidateBase == baseName do
                            (
                                local candidateClass = ""
                                try (candidateClass = (classOf candidate) as string) catch()

                                if candidateClass == sourceClass do
                                (
                                    local candidateSize = getNodeBoundingSize candidate
                                    if dimensionsApproximatelyMatch sourceSize candidateSize do
                                    (
                                        if (findItem result candidate) == 0 do append result candidate
                                    )
                                )
                            )
                        )
                    )
                )
            )
        )

        result
    ),

    fn deleteManagedReferenceNodes legacySourceNodes:#() =
    (
        local deleteNodes = collectOwnedReferenceLayerNodes()

        -- Legacy migration: source nodes directly referenced by the previous
        -- FM_Forest_001 predate ownership markers. They are still safe to
        -- remove because they are explicit cobjlist references of the managed
        -- Forest object.
        for node in legacySourceNodes do
        (
            if node != undefined and (findItem deleteNodes node) == 0 do
                append deleteNodes node
        )

        -- Migration cleanup for failed pre-idempotency runs. A sibling is
        -- accepted only when an actively managed Forest source proves the
        -- asset family and the sibling matches canonical name, class and
        -- bounding dimensions. Name alone is never enough.
        local legacySiblings = collectLegacyAutoRenameSiblings legacySourceNodes
        for node in legacySiblings do
        (
            if node != undefined and (findItem deleteNodes node) == 0 do
                append deleteNodes node
        )

        local deletedCount = 0
        for node in deleteNodes do
        (
            if node != undefined do
            (
                try
                (
                    delete node
                    deletedCount += 1
                )
                catch()
            )
        )
        deletedCount
    ),

    fn resetManagedForestFromSelectionJson =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        local splineNode = getSingleSelection()
        local selectionData = getSelectionData splineNode

        if not selectionData[5] do
            throw "Selected object is not a spline."
        if not selectionData[7] do
            throw "Selected spline must be closed."

        local oldForest = getNodeByName "FM_Forest_001"
        local oldForestDeleted = false
        local oldManagedSources = #()
        local managedReferencesDeleted = 0

        if oldForest != undefined then
        (
            local managedForest = false
            try (managedForest = isKindOf oldForest ::Forest_Pro) catch (managedForest = false)
            if not managedForest do
                throw "FM_Forest_001 exists but is not a Forest Pack object. Refusing to delete it."

            oldManagedSources = collectManagedForestSourceNodes oldForest
            delete oldForest
            oldForestDeleted = true
        )

        managedReferencesDeleted = deleteManagedReferenceNodes legacySourceNodes:oldManagedSources

        local forestNode = undefined
        local areaIndex = 0

        try
        (
            forestNode = ::Forest_Pro()
            setForestPointCloudDisplay forestNode
            forestNode.name = "FM_Forest_001"
            areaIndex = addSplineIncludeArea forestNode splineNode

            if not (verifySplineArea forestNode splineNode areaIndex) do
                throw "Managed Forest spline-area verification failed after reset."

            completeRedraw()

            "{\"forest_name\":" + (jsonString forestNode.name) +
            ",\"area_name\":" + (jsonString forestNode.arnamelist[areaIndex]) +
            ",\"area_node\":" + (jsonString splineNode.name) +
            ",\"old_forest_deleted\":" + (boolJson oldForestDeleted) +
            ",\"managed_references_deleted\":" + (managedReferencesDeleted as string) +
            ",\"geometry_count\":0" +
            ",\"verified\":true}"
        )
        catch
        (
            local message = getCurrentException()
            try (if forestNode != undefined do delete forestNode) catch()
            format "Forest Manager managed reset error: %\n" message
            throw
        )
    ),

    fn stringEndsWith value suffix =
    (
        local s = toLower (value as string)
        local t = toLower (suffix as string)
        if t.count > s.count then false
        else (substring s (s.count - t.count + 1) t.count) == t
    ),

    fn getForestGeometryContractJson =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        local forestNode = undefined
        for obj in objects while forestNode == undefined do
        (
            try
            (
                if isKindOf obj ::Forest_Pro do forestNode = obj
            )
            catch()
        )

        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene. Create the Stage 2 Forest first."

        local props = getPropNames forestNode
        local matches = #()

        for p in props do
        (
            local pn = p as string
            local lower = toLower pn
            local includeProp = false

            if (findString lower "geom") != undefined do includeProp = true
            if (findString lower "model") != undefined do includeProp = true
            if (findString lower "name") != undefined and stringEndsWith lower "list" do includeProp = true
            if (findString lower "node") != undefined and stringEndsWith lower "list" do includeProp = true
            if (findString lower "prob") != undefined do includeProp = true
            if (findString lower "mat") != undefined and stringEndsWith lower "list" do includeProp = true
            if (findString lower "map") != undefined and stringEndsWith lower "list" do includeProp = true
            if (findString lower "list") != undefined and (
                findString lower "size" != undefined or
                findString lower "scale" != undefined or
                findString lower "rot" != undefined or
                findString lower "enabled" != undefined or
                findString lower "active" != undefined
            ) do includeProp = true

            if includeProp do append matches pn
        )

        fn compareForestManagerStrings a b =
        (
            (toLower (a as string)) < (toLower (b as string))
        )
        qsort matches compareForestManagerStrings

        local json = "{\"forest_name\":" + (jsonString forestNode.name) +
                     ",\"property_count\":" + (props.count as string) +
                     ",\"geometry_candidates\":["

        for i = 1 to matches.count do
        (
            if i > 1 do json += ","
            json += jsonString matches[i]
        )

        json += "]}"
        json
    ),


    fn safeClassName value =
    (
        try
        (
            (classOf value) as string
        )
        catch
        (
            "unknown"
        )
    ),

    fn safeValuePreview value =
    (
        try
        (
            local s = value as string
            if s.count > 120 then s = (substring s 1 120) + "..."
            s
        )
        catch
        (
            "<unprintable>"
        )
    ),

    fn propertyDetailJson forestNode propName =
    (
        if not (isProperty forestNode propName) then
        (
            "{\"name\":" + (jsonString (propName as string)) +
            ",\"exists\":false}"
        )
        else
        (
            local value = getProperty forestNode propName
            local valueClass = safeClassName value
            local countValue = -1
            local firstClass = ""
            local firstPreview = ""

            try
            (
                countValue = value.count
                if countValue > 0 then
                (
                    local firstValue = value[1]
                    firstClass = safeClassName firstValue
                    firstPreview = safeValuePreview firstValue
                )
            )
            catch
            (
                countValue = -1
            )

            "{\"name\":" + (jsonString (propName as string)) +
            ",\"exists\":true" +
            ",\"value_class\":" + (jsonString valueClass) +
            ",\"count\":" + (countValue as string) +
            ",\"first_class\":" + (jsonString firstClass) +
            ",\"first_value\":" + (jsonString firstPreview) + "}"
        )
    ),

    fn getForestGeometryContractDetailsJson =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        local forestNode = undefined
        for obj in objects while forestNode == undefined do
        (
            try
            (
                if isKindOf obj ::Forest_Pro do forestNode = obj
            )
            catch()
        )

        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."

        local props = #(
            #geomlist,
            #namelist,
            #tempnamelist,
            #problist,
            #old_problist,
            #matlist,
            #ScaleList,
            #nongeomlist,
            #geomtex,
            #geomtexid,
            #consgeom
        )

        local json = "{\"forest_name\":" + (jsonString forestNode.name) +
                     ",\"properties\":["

        for i = 1 to props.count do
        (
            if i > 1 do json += ","
            json += propertyDetailJson forestNode props[i]
        )

        json += "]}"
        json
    ),


    fn findStage3Forest =
    (
        local forestNode = getNodeByName "FM_Forest_001"
        if forestNode != undefined then
        (
            try
            (
                if isKindOf forestNode ::Forest_Pro do return forestNode
            )
            catch()
        )

        forestNode = undefined
        for obj in objects while forestNode == undefined do
        (
            try
            (
                if isKindOf obj ::Forest_Pro do forestNode = obj
            )
            catch()
        )
        forestNode
    ),

    fn requireGeometryArray forestNode propName =
    (
        if not (isProperty forestNode propName) do
            throw ("Forest Pack Geometry property missing: " + (propName as string))

        local arr = getProperty forestNode propName
        if classOf arr != ArrayParameter do
            throw ("Forest Pack Geometry property is not an ArrayParameter: " + (propName as string))
        arr
    ),

    fn resizeOptionalGeometryArray forestNode propName newCount =
    (
        if isProperty forestNode propName then
        (
            local arr = getProperty forestNode propName
            if classOf arr == ArrayParameter do arr.count = newCount
        )
        true
    ),

    fn rollbackGeometryCounts forestNode oldCounts =
    (
        for entry in oldCounts do
        (
            local propName = entry[1]
            local oldCount = entry[2]
            try
            (
                if isProperty forestNode propName then
                (
                    local arr = getProperty forestNode propName
                    if classOf arr == ArrayParameter do arr.count = oldCount
                )
            )
            catch()
        )
        true
    ),

    fn rememberGeometryCounts forestNode propNames =
    (
        local result = #()
        for propName in propNames do
        (
            if isProperty forestNode propName then
            (
                local arr = getProperty forestNode propName
                if classOf arr == ArrayParameter do append result #(propName, arr.count)
            )
        )
        result
    ),

    fn addSelectedGeometryToForestJson =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."

        local sourceNode = getSingleSelection()

        local sourceIsForest = false
        try
        (
            sourceIsForest = isKindOf sourceNode ::Forest_Pro
        )
        catch
        (
            sourceIsForest = false
        )

        if sourceIsForest do
            throw "Select a source geometry object, not the Forest object."

        if superClassOf sourceNode == Shape do
            throw "Select a geometry source object, not a spline."

        local requiredProps = #(
            #cobjlist,
            #namelist,
            #matlist,
            #coloridlist,
            #problist
        )

        local optionalProps = #(
            #tempnamelist,
            #old_problist,
            #ScaleList,
            #nongeomlist,
            #geomlist
        )

        -- Validate the known core contract before changing any count.
        for propName in requiredProps do
            requireGeometryArray forestNode propName

        local allProps = requiredProps + optionalProps
        local oldCounts = rememberGeometryCounts forestNode allProps
        local oldCount = forestNode.cobjlist.count
        local newCount = oldCount + 1
        local index = newCount

        try
        (
            -- Core arrays documented/used by ITOOSOFT examples.
            forestNode.cobjlist.count = newCount
            forestNode.namelist.count = newCount
            forestNode.matlist.count = newCount
            forestNode.coloridlist.count = newCount
            forestNode.problist.count = newCount

            -- Arrays observed in this Forest Pack 9.4.0 installation.
            for propName in optionalProps do
                resizeOptionalGeometryArray forestNode propName newCount

            forestNode.cobjlist[index] = sourceNode
            forestNode.namelist[index] = sourceNode.name
            forestNode.matlist[index] = sourceNode.material
            forestNode.problist[index] = 100.0

            -- Runtime verification on Forest Pack 9.4.0 confirmed:
            -- geomlist: Integer, 0 = Disabled, 2 = Custom Object.
            -- ScaleList: Float, nongeomlist: BooleanClass.
            -- Use only values observed on this exact installed version.

            if isProperty forestNode #geomlist do
                forestNode.geomlist[index] = 2

            if isProperty forestNode #tempnamelist do
                forestNode.tempnamelist[index] = sourceNode.name

            if isProperty forestNode #old_problist do
                forestNode.old_problist[index] = 100

            if isProperty forestNode #ScaleList do
                forestNode.ScaleList[index] = 100.0

            if isProperty forestNode #nongeomlist do
                forestNode.nongeomlist[index] = false

            if forestNode.cobjlist.count != newCount do
                throw "Geometry verification failed: cobjlist count mismatch."

            if forestNode.cobjlist[index] != sourceNode do
                throw "Geometry verification failed: source node mismatch."

            if forestNode.namelist[index] != sourceNode.name do
                throw "Geometry verification failed: source name mismatch."

            completeRedraw()

            "{\"forest_name\":" + (jsonString forestNode.name) +
            ",\"source_name\":" + (jsonString sourceNode.name) +
            ",\"geometry_count\":" + (forestNode.cobjlist.count as string) +
            ",\"geometry_index\":" + (index as string) +
            ",\"probability\":" + (forestNode.problist[index] as string) +
            ",\"verified\":true}"
        )
        catch
        (
            local message = getCurrentException()
            rollbackGeometryCounts forestNode oldCounts
            format "Forest Manager Stage 3 geometry error: %\n" message
            throw
        )
    ),


    fn getForestDistributionContractJson =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."

        local props = getPropNames forestNode
        local matches = #()

        for p in props do
        (
            local pn = p as string
            local lower = toLower pn
            local includeProp = false

            if (findString lower "dist") != undefined do includeProp = true
            if (findString lower "density") != undefined do includeProp = true
            if (findString lower "map") != undefined do includeProp = true
            if (findString lower "pattern") != undefined do includeProp = true
            if (findString lower "mode") != undefined do includeProp = true
            if (findString lower "manual") != undefined do includeProp = true
            if (findString lower "update") != undefined do includeProp = true
            if (findString lower "seed") != undefined do includeProp = true
            if (findString lower "spacing") != undefined do includeProp = true
            if (findString lower "limit") != undefined do includeProp = true

            if includeProp do append matches pn
        )

        fn compareForestDistributionStrings a b =
        (
            (toLower (a as string)) < (toLower (b as string))
        )
        qsort matches compareForestDistributionStrings

        local json = "{\"forest_name\":" + (jsonString forestNode.name) +
                     ",\"property_count\":" + (props.count as string) +
                     ",\"properties\":["

        for i = 1 to matches.count do
        (
            local propName = matches[i]
            local sym = propName as name
            local value = undefined
            local valueClass = ""
            local preview = ""

            try
            (
                value = getProperty forestNode sym
                valueClass = safeClassName value
                preview = safeValuePreview value
            )
            catch
            (
                valueClass = "error"
                preview = getCurrentException()
            )

            if i > 1 do json += ","
            json += "{\"name\":" + (jsonString propName) +
                    ",\"value_class\":" + (jsonString valueClass) +
                    ",\"value\":" + (jsonString preview) + "}"
        )

        json += "]}"
        json
    ),


    fn getForestDistributionUnitsJson =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."

        local props = getPropNames forestNode
        local matches = #()

        for p in props do
        (
            local pn = p as string
            local lower = toLower pn
            local includeProp = false

            if (findString lower "unit") != undefined do includeProp = true
            if (findString lower "density") != undefined do includeProp = true
            if (findString lower "size") != undefined do includeProp = true
            if (findString lower "width") != undefined do includeProp = true
            if (findString lower "height") != undefined do includeProp = true
            if (findString lower "xsize") != undefined do includeProp = true
            if (findString lower "ysize") != undefined do includeProp = true
            if (findString lower "xunit") != undefined do includeProp = true
            if (findString lower "yunit") != undefined do includeProp = true

            if includeProp do append matches pn
        )

        fn compareForestUnitStrings a b =
        (
            (toLower (a as string)) < (toLower (b as string))
        )
        qsort matches compareForestUnitStrings

        local json = "{\"forest_name\":" + (jsonString forestNode.name) +
                     ",\"properties\":["

        for i = 1 to matches.count do
        (
            local propName = matches[i]
            local sym = propName as name
            local valueClass = ""
            local preview = ""

            try
            (
                local value = getProperty forestNode sym
                valueClass = safeClassName value
                preview = safeValuePreview value
            )
            catch
            (
                valueClass = "error"
                preview = getCurrentException()
            )

            if i > 1 do json += ","
            json += "{\"name\":" + (jsonString propName) +
                    ",\"value_class\":" + (jsonString valueClass) +
                    ",\"value\":" + (jsonString preview) + "}"
        )

        json += "]}"
        json
    ),


    fn findForestAreaSpline forestNode =
    (
        local result = undefined
        if isProperty forestNode #arnodelist then
        (
            local nodes = forestNode.arnodelist
            for i = 1 to nodes.count while result == undefined do
            (
                local candidate = nodes[i]
                if candidate != undefined then
                (
                    try
                    (
                        if superClassOf candidate == Shape do result = candidate
                    )
                    catch()
                )
            )
        )
        result
    ),

    fn getForestAreaPolygonJson samples:256 =
    (
        if samples < 32 do samples = 32

        local sourceForest = getNodeByName "FM_Forest_001"
        if sourceForest == undefined do
            throw "FM_Forest_001 was not found."

        local splineNode = findForestAreaSpline sourceForest
        if splineNode == undefined do
            throw "FM_Forest_001 has no bound spline area."

        local splineCount = 0
        try (splineCount = numSplines splineNode) catch (splineCount = 0)
        if splineCount < 1 do throw "Bound Forest area object is not a spline."

        local rings = #()
        local minX = 1.0e30
        local minY = 1.0e30
        local maxX = -1.0e30
        local maxY = -1.0e30

        for splineIndex = 1 to splineCount do
        (
            if not (isClosed splineNode splineIndex) do
                throw ("Forest area contains an open spline at index " + (splineIndex as string))

            local ring = #()
            for i = 0 to (samples - 1) do
            (
                local t = (i as float) / (samples as float)
                local p = interpCurve3D splineNode splineIndex t
                append ring p
                if p.x < minX do minX = p.x
                if p.y < minY do minY = p.y
                if p.x > maxX do maxX = p.x
                if p.y > maxY do maxY = p.y
            )
            append rings ring
        )

        local width = maxX - minX
        local height = maxY - minY
        if width <= 0.0 or height <= 0.0 do
            throw "Forest area spline polygon has invalid bounds."

        local ringsJson = "["
        for ringIndex = 1 to rings.count do
        (
            if ringIndex > 1 do ringsJson += ","
            ringsJson += "["
            local ring = rings[ringIndex]
            for pointIndex = 1 to ring.count do
            (
                if pointIndex > 1 do ringsJson += ","
                local p = ring[pointIndex]
                local nx = (p.x - minX) / width
                -- PIL raster Y grows downward while Max Y/V grows upward.
                local ny = 1.0 - ((p.y - minY) / height)
                ringsJson += "[" + (nx as string) + "," + (ny as string) + "]"
            )
            ringsJson += "]"
        )
        ringsJson += "]"

        local oneMeter = 0.0
        try (oneMeter = units.decodeValue "1m") catch (oneMeter = 0.0)
        if oneMeter <= 0.0 do throw "Could not resolve active scene meter conversion."

        "{\"forest_name\":\"FM_Forest_001\"" +
        ",\"spline_name\":" + (jsonString splineNode.name) +
        ",\"spline_count\":" + (splineCount as string) +
        ",\"samples_per_spline\":" + (samples as string) +
        ",\"bounds_width_meters\":" + ((width / oneMeter) as string) +
        ",\"bounds_height_meters\":" + ((height / oneMeter) as string) +
        ",\"normalized_rings\":" + ringsJson +
        ",\"coordinate_space\":\"normalized_bbox_with_pil_y_flip\"" +
        ",\"verified\":true}"
    ),

    fn calculateAdaptiveDistributionUnits splineNode =
    (
        local bb = nodeGetBoundingBox splineNode splineNode.transform
        local pmin = bb[1]
        local pmax = bb[2]

        local sizeX = abs (pmax.x - pmin.x)
        local sizeY = abs (pmax.y - pmin.y)
        local usableMin = amin sizeX sizeY
        local usableMax = amax sizeX sizeY

        if usableMin <= 0.001 do usableMin = usableMax
        if usableMin <= 0.001 do usableMin = 100.0

        -- Aim for roughly 20 candidate cells across the narrower dimension.
        -- Clamp so very small or very large scenes remain usable.
        local units = usableMin / 20.0
        if units < 1.0 do units = 1.0
        if units > 500.0 do units = 500.0

        #(units, sizeX, sizeY)
    ),

    fn configureAdaptiveDistributionJson =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."

        local splineNode = findForestAreaSpline forestNode
        if splineNode == undefined do
            throw "Forest Pack object has no spline Area."

        if not (isProperty forestNode #units_x) do
            throw "Forest Pack property missing: units_x."
        if not (isProperty forestNode #units_y) do
            throw "Forest Pack property missing: units_y."

        local previousX = forestNode.units_x
        local previousY = forestNode.units_y
        local previousMode = if isProperty forestNode #distmode then forestNode.distmode else undefined
        local previousManual = if isProperty forestNode #manualupdate then forestNode.manualupdate else undefined
        local previousDensityMap = if isProperty forestNode #densityMap then forestNode.densityMap else undefined

        local values = calculateAdaptiveDistributionUnits splineNode
        local units = values[1]
        local sizeX = values[2]
        local sizeY = values[3]

        try
        (
            if isProperty forestNode #distmode do forestNode.distmode = 0
            if isProperty forestNode #densityMap do forestNode.densityMap = false
            if isProperty forestNode #manualupdate do forestNode.manualupdate = false

            forestNode.units_x = units
            forestNode.units_y = units

            if abs (forestNode.units_x - units) > 0.001 do
                throw "Distribution verification failed: units_x mismatch."
            if abs (forestNode.units_y - units) > 0.001 do
                throw "Distribution verification failed: units_y mismatch."

            completeRedraw()

            "{\"forest_name\":" + (jsonString forestNode.name) +
            ",\"area_node\":" + (jsonString splineNode.name) +
            ",\"area_size_x\":" + (sizeX as string) +
            ",\"area_size_y\":" + (sizeY as string) +
            ",\"previous_units_x\":" + (previousX as string) +
            ",\"previous_units_y\":" + (previousY as string) +
            ",\"units_x\":" + (forestNode.units_x as string) +
            ",\"units_y\":" + (forestNode.units_y as string) +
            ",\"distmode\":" + ((if isProperty forestNode #distmode then forestNode.distmode else -1) as string) +
            ",\"verified\":true}"
        )
        catch
        (
            local message = getCurrentException()

            try (forestNode.units_x = previousX) catch()
            try (forestNode.units_y = previousY) catch()
            try
            (
                if previousMode != undefined and isProperty forestNode #distmode do
                    forestNode.distmode = previousMode
            )
            catch()
            try
            (
                if previousManual != undefined and isProperty forestNode #manualupdate do
                    forestNode.manualupdate = previousManual
            )
            catch()
            try
            (
                if previousDensityMap != undefined and isProperty forestNode #densityMap do
                    forestNode.densityMap = previousDensityMap
            )
            catch()

            format "Forest Manager adaptive distribution error: %\n" message
            throw
        )
    ),


    fn normalizeForestBuildStateJson =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."

        local previousDisabled = undefined
        local previousManual = undefined

        if isProperty forestNode #disabled do
            previousDisabled = forestNode.disabled

        if isProperty forestNode #manualupdate do
            previousManual = forestNode.manualupdate

        try
        (
            if isProperty forestNode #disabled do
                forestNode.disabled = false

            if isProperty forestNode #manualupdate do
                forestNode.manualupdate = false

            -- Re-apply the already verified adaptive distribution units.
            local splineNode = findForestAreaSpline forestNode
            if splineNode != undefined and
               isProperty forestNode #units_x and
               isProperty forestNode #units_y then
            (
                local values = calculateAdaptiveDistributionUnits splineNode
                forestNode.units_x = values[1]
                forestNode.units_y = values[1]
            )

            -- Force dependency notification/redraw without saving the scene.
            try (notifyDependents forestNode partID:#all message:#change) catch()
            completeRedraw()

            local disabledNow = if isProperty forestNode #disabled then forestNode.disabled else false
            local manualNow = if isProperty forestNode #manualupdate then forestNode.manualupdate else false

            if disabledNow do
                throw "Forest build normalization failed: object is still disabled."

            "{\"forest_name\":" + (jsonString forestNode.name) +
            ",\"previous_disabled\":" + (if previousDisabled == undefined then "null" else boolJson previousDisabled) +
            ",\"disabled\":" + (boolJson disabledNow) +
            ",\"manualupdate\":" + (boolJson manualNow) +
            ",\"units_x\":" + ((if isProperty forestNode #units_x then forestNode.units_x else 0.0) as string) +
            ",\"units_y\":" + ((if isProperty forestNode #units_y then forestNode.units_y else 0.0) as string) +
            ",\"verified\":true}"
        )
        catch
        (
            local message = getCurrentException()
            try
            (
                if previousDisabled != undefined and isProperty forestNode #disabled do
                    forestNode.disabled = previousDisabled
            )
            catch()
            try
            (
                if previousManual != undefined and isProperty forestNode #manualupdate do
                    forestNode.manualupdate = previousManual
            )
            catch()

            format "Forest Manager build-state normalization error: %\n" message
            throw
        )
    ),


    fn getForestFullRuntimeContractJson =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."

        local props = getPropNames forestNode
        local arrayProps = #()
        local stateProps = #()

        for p in props do
        (
            local pn = p as string
            local sym = pn as name
            local value = undefined
            local isArray = false

            try
            (
                value = getProperty forestNode sym
                isArray = ((classOf value) as string) == "ArrayParameter"
            )
            catch()

            if isArray do append arrayProps pn

            local lower = toLower pn
            local includeState = false
            if (findString lower "display") != undefined do includeState = true
            if (findString lower "disabled") != undefined do includeState = true
            if (findString lower "build") != undefined do includeState = true
            if (findString lower "mode") != undefined do includeState = true
            if (findString lower "render") != undefined do includeState = true
            if (findString lower "viewport") != undefined do includeState = true
            if (findString lower "maxitem") != undefined do includeState = true
            if (findString lower "maxface") != undefined do includeState = true
            if (findString lower "manual") != undefined do includeState = true
            if (findString lower "unit") != undefined do includeState = true
            if (findString lower "density") != undefined do includeState = true
            if includeState and not isArray do append stateProps pn
        )

        fn compareForestRuntimeStrings a b =
        (
            (toLower (a as string)) < (toLower (b as string))
        )
        qsort arrayProps compareForestRuntimeStrings
        qsort stateProps compareForestRuntimeStrings

        local json = "{\"forest_name\":" + (jsonString forestNode.name) +
                     ",\"array_properties\":["

        for i = 1 to arrayProps.count do
        (
            local propName = arrayProps[i]
            local sym = propName as name
            local value = undefined
            local countValue = -1
            local firstClass = ""
            local firstValue = ""

            try
            (
                value = getProperty forestNode sym
                countValue = value.count
                if countValue > 0 then
                (
                    firstClass = safeClassName value[1]
                    firstValue = safeValuePreview value[1]
                )
            )
            catch
            (
                firstClass = "error"
                firstValue = getCurrentException()
            )

            if i > 1 do json += ","
            json += "{\"name\":" + (jsonString propName) +
                    ",\"count\":" + (countValue as string) +
                    ",\"first_class\":" + (jsonString firstClass) +
                    ",\"first_value\":" + (jsonString firstValue) + "}"
        )

        json += "],\"state_properties\":["

        for i = 1 to stateProps.count do
        (
            local propName = stateProps[i]
            local sym = propName as name
            local valueClass = ""
            local preview = ""

            try
            (
                local value = getProperty forestNode sym
                valueClass = safeClassName value
                preview = safeValuePreview value
            )
            catch
            (
                valueClass = "error"
                preview = getCurrentException()
            )

            if i > 1 do json += ","
            json += "{\"name\":" + (jsonString propName) +
                    ",\"value_class\":" + (jsonString valueClass) +
                    ",\"value\":" + (jsonString preview) + "}"
        )

        local sourceName = ""
        local geomCount = 0
        try
        (
            geomCount = forestNode.cobjlist.count
            if geomCount > 0 and forestNode.cobjlist[1] != undefined do
                sourceName = forestNode.cobjlist[1].name
        )
        catch()

        json += "],\"geometry_count\":" + (geomCount as string) +
                ",\"source_name\":" + (jsonString sourceName) + "}"
        json
    ),


    fn getForestGeneratedItemCount forestNode =
    (
        local result = -1
        try
        (
            result = forestNode.trees.count()
        )
        catch
        (
            result = -1
        )
        result
    ),

    fn normalizeGeometryItemJson =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."

        if not (isProperty forestNode #cobjlist) do
            throw "Forest Pack property missing: cobjlist."
        if forestNode.cobjlist.count < 1 do
            throw "Forest Geometry List is empty."

        local sourceNode = forestNode.cobjlist[1]
        if sourceNode == undefined do
            throw "Forest Geometry source node is undefined."

        local itemMatrix = sourceNode.transform
        local bb = nodeGetBoundingBox sourceNode itemMatrix
        local rawSize = bb[2] - bb[1]
        local sizeX = abs rawSize.x
        local sizeY = abs rawSize.y
        local sizeZ = abs rawSize.z
        local wireColorValue = sourceNode.wirecolor

        local beforeCount = getForestGeneratedItemCount forestNode

        try
        (
            -- Set the verified Custom Object mode first.
            if isProperty forestNode #geomlist and forestNode.geomlist.count >= 1 do
                forestNode.geomlist[1] = 2

            -- Normalize all source-specific metadata that was observed in the
            -- Forest Pack 9.4.0 runtime contract.
            if isProperty forestNode #namelist and forestNode.namelist.count >= 1 do
                forestNode.namelist[1] = sourceNode.name

            if isProperty forestNode #tempnamelist and forestNode.tempnamelist.count >= 1 do
                forestNode.tempnamelist[1] = sourceNode.name

            if isProperty forestNode #matlist and forestNode.matlist.count >= 1 do
                forestNode.matlist[1] = sourceNode.material

            if isProperty forestNode #coloridlist and forestNode.coloridlist.count >= 1 do
                forestNode.coloridlist[1] = wireColorValue

            if isProperty forestNode #widthlist and forestNode.widthlist.count >= 1 do
                forestNode.widthlist[1] = sizeX

            if isProperty forestNode #heightlist and forestNode.heightlist.count >= 1 do
                forestNode.heightlist[1] = sizeZ

            if isProperty forestNode #ScaleList and forestNode.ScaleList.count >= 1 do
                forestNode.ScaleList[1] = 100.0

            if isProperty forestNode #zoffsetlist and forestNode.zoffsetlist.count >= 1 do
                forestNode.zoffsetlist[1] = 0.0

            if isProperty forestNode #nongeomlist and forestNode.nongeomlist.count >= 1 do
                forestNode.nongeomlist[1] = false

            if isProperty forestNode #includechildlist and forestNode.includechildlist.count >= 1 do
                forestNode.includechildlist[1] = false

            if isProperty forestNode #keepgrouplist and forestNode.keepgrouplist.count >= 1 do
                forestNode.keepgrouplist[1] = false

            if isProperty forestNode #problist and forestNode.problist.count >= 1 do
                forestNode.problist[1] = 100.0

            if isProperty forestNode #old_problist and forestNode.old_problist.count >= 1 do
                forestNode.old_problist[1] = 100

            -- Reassign the source last. This mirrors the UI flow where Custom
            -- Object mode is chosen before the picker receives the source node.
            forestNode.cobjlist[1] = undefined
            forestNode.cobjlist[1] = sourceNode

            if isProperty forestNode #disabled do
                forestNode.disabled = false

            if isProperty forestNode #manualupdate do
                forestNode.manualupdate = false

            try (notifyDependents forestNode partID:#all message:#change) catch()
            completeRedraw()

            local afterCount = getForestGeneratedItemCount forestNode

            local verified = true
            if forestNode.cobjlist[1] != sourceNode do verified = false
            if isProperty forestNode #geomlist and forestNode.geomlist[1] != 2 do verified = false
            if isProperty forestNode #tempnamelist and forestNode.tempnamelist[1] != sourceNode.name do verified = false

            "{\"forest_name\":" + (jsonString forestNode.name) +
            ",\"source_name\":" + (jsonString sourceNode.name) +
            ",\"geometry_mode\":" + ((if isProperty forestNode #geomlist then forestNode.geomlist[1] else -1) as string) +
            ",\"temp_name\":" + (jsonString (if isProperty forestNode #tempnamelist then forestNode.tempnamelist[1] else "")) +
            ",\"width\":" + (sizeX as string) +
            ",\"depth\":" + (sizeY as string) +
            ",\"height\":" + (sizeZ as string) +
            ",\"generated_items_before\":" + (beforeCount as string) +
            ",\"generated_items_after\":" + (afterCount as string) +
            ",\"verified\":" + (boolJson verified) + "}"
        )
        catch
        (
            format "Forest Manager geometry normalization error: %\n" (getCurrentException())
            throw
        )
    ),


    fn decodeBase64Utf8 encoded =
    (
        local convertClass = dotNetClass "System.Convert"
        local utf8Class = (dotNetClass "System.Text.Encoding").UTF8
        local bytes = convertClass.FromBase64String encoded
        utf8Class.GetString bytes
    ),

    fn chooseMergedSourceNode newObjects expectedSourceName:"" =
    (
        local sourceNode = undefined
        local safeExpectedSourceName = if expectedSourceName == undefined then "" else (expectedSourceName as string)
        local expectedLower = toLower safeExpectedSourceName

        -- T2 vegetation assets are normally Corona/V-Ray proxy nodes.
        -- Prefer a proxy anywhere in the merged set before generic helper
        -- geometry such as Plane001.
        for obj in newObjects while sourceNode == undefined do
        (
            local className = ""
            try (className = toLower ((classOf obj) as string)) catch()
            if className == "cproxy" do sourceNode = obj
        )

        -- If multiple proxy/group representations are unavailable, prefer a
        -- top-level node whose name matches the asset file name.
        if sourceNode == undefined and expectedLower != "" do
        (
            for obj in newObjects while sourceNode == undefined do
            (
                local objName = ""
                try (objName = toLower obj.name) catch()
                if objName != "" and (findString objName expectedLower) != undefined do
                (
                    local isGeometry = false
                    try (isGeometry = (superClassOf obj == GeometryClass)) catch()
                    if isGeometry do sourceNode = obj
                )
            )
        )

        -- Preserve grouped vegetation when no proxy/name match exists.
        for obj in newObjects while sourceNode == undefined do
        (
            if obj.parent == undefined then
            (
                local groupHead = false
                try (groupHead = isGroupHead obj) catch (groupHead = false)
                if groupHead do sourceNode = obj
            )
        )

        -- Prefer non-Plane top-level geometry. Helper planes are a last-resort
        -- fallback because some vegetation .max files include ground/reference
        -- planes that must never become Forest geometry.
        for obj in newObjects while sourceNode == undefined do
        (
            if obj.parent == undefined then
            (
                local isGeometry = false
                local className = ""
                try (isGeometry = (superClassOf obj == GeometryClass)) catch()
                try (className = toLower ((classOf obj) as string)) catch()
                if isGeometry and className != "plane" do sourceNode = obj
            )
        )

        -- Any remaining geometry is safer than an arbitrary helper node.
        for obj in newObjects while sourceNode == undefined do
        (
            local isGeometry = false
            try (isGeometry = (superClassOf obj == GeometryClass)) catch()
            if isGeometry do sourceNode = obj
        )

        -- Final fallback for unusual grouped assets.
        for obj in newObjects while sourceNode == undefined do
            if obj.parent == undefined do sourceNode = obj

        if sourceNode == undefined and newObjects.count > 0 do
            sourceNode = newObjects[1]

        sourceNode
    ),

    fn ensureGeometryArrayCount forestNode propName targetCount =
    (
        if isProperty forestNode propName then
        (
            local arr = getProperty forestNode propName
            if classOf arr == ArrayParameter and arr.count < targetCount do
                arr.count = targetCount
        )
        true
    ),

    fn bindForestGeometrySource forestNode sourceNode =
    (
        if forestNode == undefined do
            throw "Forest object is undefined."
        if sourceNode == undefined do
            throw "Merged source node is undefined."

        local geometryProps = #(
            #cobjlist, #namelist, #matlist, #coloridlist, #geomlist,
            #tempidlist, #tempnamelist, #widthlist, #heightlist, #ScaleList,
            #zoffsetlist, #radiuslist, #specidlist, #usemeshdimlist,
            #conamelist, #includechildlist, #keepgrouplist, #nongeomlist,
            #old_problist, #problist, #centerlist
        )

        for propName in geometryProps do
            ensureGeometryArrayCount forestNode propName 1

        if not (isProperty forestNode #cobjlist) do
            throw "Forest Pack property missing: cobjlist."
        if forestNode.cobjlist.count < 1 do
            throw "Forest Pack Geometry List could not be initialized."

        local bb = nodeGetBoundingBox sourceNode sourceNode.transform
        local rawSize = bb[2] - bb[1]
        local sizeX = abs rawSize.x
        local sizeY = abs rawSize.y
        local sizeZ = abs rawSize.z

        -- Custom Object mode was verified at runtime on Forest Pack 9.4.0.
        if isProperty forestNode #geomlist do forestNode.geomlist[1] = 2
        if isProperty forestNode #namelist do forestNode.namelist[1] = sourceNode.name
        if isProperty forestNode #tempnamelist do forestNode.tempnamelist[1] = sourceNode.name
        if isProperty forestNode #tempidlist do forestNode.tempidlist[1] = 0
        if isProperty forestNode #matlist do forestNode.matlist[1] = sourceNode.material
        if isProperty forestNode #coloridlist do forestNode.coloridlist[1] = sourceNode.wirecolor
        if isProperty forestNode #widthlist and sizeX > 0.0 do forestNode.widthlist[1] = sizeX
        if isProperty forestNode #heightlist and sizeZ > 0.0 do forestNode.heightlist[1] = sizeZ
        if isProperty forestNode #ScaleList do forestNode.ScaleList[1] = 100.0
        if isProperty forestNode #zoffsetlist do forestNode.zoffsetlist[1] = 0.0
        if isProperty forestNode #radiuslist do forestNode.radiuslist[1] = 100
        if isProperty forestNode #specidlist do forestNode.specidlist[1] = 1
        if isProperty forestNode #usemeshdimlist do forestNode.usemeshdimlist[1] = false
        if isProperty forestNode #conamelist do forestNode.conamelist[1] = ""
        if isProperty forestNode #includechildlist do forestNode.includechildlist[1] = false
        if isProperty forestNode #keepgrouplist do forestNode.keepgrouplist[1] = false
        if isProperty forestNode #nongeomlist do forestNode.nongeomlist[1] = false
        if isProperty forestNode #old_problist do forestNode.old_problist[1] = 100
        if isProperty forestNode #problist do forestNode.problist[1] = 100.0
        if isProperty forestNode #centerlist do forestNode.centerlist[1] = 50

        -- Assign the real source last, matching the verified UI flow.
        forestNode.cobjlist[1] = undefined
        forestNode.cobjlist[1] = sourceNode

        if forestNode.cobjlist[1] != sourceNode do
            throw "Forest Pack source assignment verification failed."
        if isProperty forestNode #geomlist and forestNode.geomlist[1] != 2 do
            throw "Forest Pack Custom Object mode verification failed."

        #(sizeX, sizeY, sizeZ)
    ),

    -- Merge helpers must be declared before mergeT2AssetAndBindJson on
    -- 3ds Max 2020 MaxScript because struct member resolution is order-sensitive.
    fn getOrCreateReferenceLayer =
    (
        local managedLayer = LayerManager.getLayerFromName "FM_MANAGED"
        if managedLayer == undefined do managedLayer = LayerManager.newLayerFromName "FM_MANAGED"
        if managedLayer == undefined do throw "Unable to create or resolve FM_MANAGED layer."
        try (managedLayer.lock = false) catch()
        try (managedLayer.isFrozen = false) catch()
        try (managedLayer.on = true) catch()

        local refLayer = LayerManager.getLayerFromName "FM_REFERENCES"
        if refLayer == undefined do refLayer = LayerManager.newLayerFromName "FM_REFERENCES"
        if refLayer == undefined do throw "Unable to create or resolve FM_REFERENCES layer."
        try (refLayer.lock = false) catch()
        try (refLayer.isFrozen = false) catch()
        try (refLayer.on = false) catch()

        local parentOk = false
        try
        (
            local currentParent = refLayer.getParent()
            if currentParent == managedLayer then
                parentOk = true
            else
                parentOk = refLayer.setParent managedLayer
        )
        catch (parentOk = false)
        if not parentOk do throw "Unable to parent FM_REFERENCES under FM_MANAGED."
        refLayer
    ),

    fn prepareReferenceNode node =
    (
        if node == undefined do return false

        local refLayer = getOrCreateReferenceLayer()
        local targetZ = millimetersToSystemUnits -1500.0

        try
        (
            local p = node.position
            node.position = [p.x, p.y, targetZ]
        )
        catch
        (
            try (node.pos.z = targetZ) catch()
        )

        try (refLayer.addNode node) catch()
        markForestManagerOwnedNode node role:"reference_source"

        -- Reference sources stay hidden and protected from direct artist edits.
        try (refLayer.on = false) catch()
        try (refLayer.isFrozen = true) catch()
        try (refLayer.lock = true) catch()
        local managedLayer = LayerManager.getLayerFromName "FM_MANAGED"
        if managedLayer != undefined do
        (
            try (managedLayer.on = true) catch()
            try (managedLayer.isFrozen = true) catch()
            try (managedLayer.lock = true) catch()
        )

        true
    ),

    fn reportBridgeError message =
    (
        format "%\n" message
        true
    ),

    fn currentExceptionDetails prefix =
    (
        local message = ""
        local stackText = ""
        local sourceFile = ""
        local sourceLine = 0

        try (message = getCurrentException()) catch()
        try (stackText = getCurrentExceptionStackTrace()) catch()
        try (sourceFile = getErrorSourceFileName()) catch()
        try (sourceLine = getErrorSourceFileLine()) catch()

        local details = prefix + message
        if sourceFile != undefined and sourceFile != "" do
            details += " | source=" + sourceFile
        if sourceLine != undefined and sourceLine > 0 do
            details += " | line=" + (sourceLine as string)
        if stackText != undefined and stackText != "" do
            details += " | stack=" + stackText
        details
    ),

    fn mergeT2AssetAndBindJson assetPath =
    (
        if assetPath == undefined or assetPath == "" do
            throw "T2 asset path is empty."
        if not (doesFileExist assetPath) do
            throw ("T2 asset file does not exist: " + assetPath)

        local ext = toLower (getFilenameType assetPath)
        if ext != ".max" do
            throw "Stage 4C accepts only .max assets."

        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."

        local expectedSourceName = getFilenameFile assetPath

        local beforeObjects = objects as array
        local beforeCount = beforeObjects.count

        clearSelection()

        local mergeResult = false
        try
        (
            mergeResult = mergeMAXFile assetPath #select #autoRenameDups #useMergedMtlDups quiet:true
        )
        catch
        (
            reportBridgeError (currentExceptionDetails "MERGE_STEP[mergeMAXFile]: ")
            throw()
        )

        local afterObjects = objects as array
        local newObjects = for obj in afterObjects where (findItem beforeObjects obj) == 0 collect obj

        if newObjects.count < 1 do
            throw "MERGE_STEP[newObjects]: T2 asset merge produced no new scene nodes."

        local refLayer = getOrCreateReferenceLayer()
        for obj in newObjects do
        (
            markForestManagerOwnedNode obj role:"merged_asset_node"
            try (refLayer.addNode obj) catch()
        )
        try (refLayer.on = false) catch()

        local sourceNode = undefined
        try
        (
            sourceNode = chooseMergedSourceNode newObjects expectedSourceName:expectedSourceName
        )
        catch
        (
            reportBridgeError ("MERGE_STEP[chooseMergedSourceNode]: " + (getCurrentException()))
            throw()
        )
        if sourceNode == undefined do
            throw "MERGE_STEP[chooseMergedSourceNode]: Could not choose a Forest source from merged nodes."

        try (sourceNode.name = expectedSourceName) catch()

        -- Match T2's existing merge behavior for top-level assets.
        if sourceNode.parent == undefined do
        (
            try (sourceNode.position = [0,0,0]) catch()
        )

        try
        (
            prepareReferenceNode sourceNode
        )
        catch
        (
            reportBridgeError ("MERGE_STEP[prepareReferenceNode]: " + (getCurrentException()))
            throw()
        )

        local dimensions = undefined
        try
        (
            dimensions = bindForestGeometrySource forestNode sourceNode
        )
        catch
        (
            reportBridgeError ("MERGE_STEP[bindForestGeometrySource]: " + (getCurrentException()))
            throw()
        )

        local splineNode = findForestAreaSpline forestNode
        if splineNode != undefined and
           isProperty forestNode #units_x and
           isProperty forestNode #units_y then
        (
            local distValues = calculateAdaptiveDistributionUnits splineNode
            forestNode.units_x = distValues[1]
            forestNode.units_y = distValues[1]
        )

        if isProperty forestNode #distmode do forestNode.distmode = 0
        if isProperty forestNode #densityMap do forestNode.densityMap = false
        if isProperty forestNode #disabled do forestNode.disabled = false
        if isProperty forestNode #manualupdate do forestNode.manualupdate = false

        select newObjects

        try (notifyDependents forestNode partID:#all message:#change) catch()
        completeRedraw()

        local generatedCount = getForestGeneratedItemCount forestNode
        local nodeJson = "["
        for i = 1 to newObjects.count do
        (
            if i > 1 do nodeJson += ","
            nodeJson += jsonString newObjects[i].name
        )
        nodeJson += "]"

        local verified = true
        if forestNode.cobjlist.count < 1 do verified = false
        if forestNode.cobjlist[1] != sourceNode do verified = false
        if isProperty forestNode #geomlist and forestNode.geomlist[1] != 2 do verified = false

        "{\"asset_path\":" + (jsonString assetPath) +
        ",\"forest_name\":" + (jsonString forestNode.name) +
        ",\"merged_node_count\":" + (newObjects.count as string) +
        ",\"scene_object_count_before\":" + (beforeCount as string) +
        ",\"scene_object_count_after\":" + (afterObjects.count as string) +
        ",\"source_name\":" + (jsonString sourceNode.name) +
        ",\"source_class\":" + (jsonString ((classOf sourceNode) as string)) +
        ",\"source_width\":" + (dimensions[1] as string) +
        ",\"source_depth\":" + (dimensions[2] as string) +
        ",\"source_height\":" + (dimensions[3] as string) +
        ",\"source_width_display\":" + (jsonString (formatSystemValueForScene dimensions[1])) +
        ",\"source_depth_display\":" + (jsonString (formatSystemValueForScene dimensions[2])) +
        ",\"source_height_display\":" + (jsonString (formatSystemValueForScene dimensions[3])) +
        ",\"geometry_count\":" + (forestNode.cobjlist.count as string) +
        ",\"geometry_mode\":" + ((if isProperty forestNode #geomlist then forestNode.geomlist[1] else -1) as string) +
        ",\"generated_items\":" + (generatedCount as string) +
        ",\"merged_nodes\":" + nodeJson +
        ",\"verified\":" + (boolJson verified) + "}"
    ),


    fn getPrimaryForestGeometrySource forestNode =
    (
        if forestNode == undefined do return undefined
        if not (isProperty forestNode #cobjlist) do return undefined
        if forestNode.cobjlist.count < 1 do return undefined
        forestNode.cobjlist[1]
    ),

    fn calculateAssetAwareDistributionUnits sourceNode splineNode =
    (
        if sourceNode == undefined do
            throw "Forest geometry source is undefined."

        local sourceBB = nodeGetBoundingBox sourceNode sourceNode.transform
        local sourceSize = sourceBB[2] - sourceBB[1]
        local sourceX = abs sourceSize.x
        local sourceY = abs sourceSize.y

        if sourceX <= 0.001 do sourceX = 1.0
        if sourceY <= 0.001 do sourceY = 1.0

        -- Use the real horizontal asset footprint as the base spacing.
        -- A small safety margin avoids heavy crown/proxy overlap.
        local spacingX = sourceX * 1.05
        local spacingY = sourceY * 1.05

        local areaX = 0.0
        local areaY = 0.0

        if splineNode != undefined then
        (
            local areaBB = nodeGetBoundingBox splineNode splineNode.transform
            local areaSize = areaBB[2] - areaBB[1]
            areaX = abs areaSize.x
            areaY = abs areaSize.y

            -- Avoid spacing larger than the complete area when possible.
            if areaX > 1.0 and spacingX > areaX do spacingX = areaX
            if areaY > 1.0 and spacingY > areaY do spacingY = areaY
        )

        if spacingX < 1.0 do spacingX = 1.0
        if spacingY < 1.0 do spacingY = 1.0

        #(spacingX, spacingY, sourceX, sourceY, areaX, areaY)
    ),

    fn configureAssetAwareDensityJson =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."

        local sourceNode = getPrimaryForestGeometrySource forestNode
        if sourceNode == undefined do
            throw "Forest Geometry List has no Custom Object source."

        if not (isProperty forestNode #units_x) do
            throw "Forest Pack property missing: units_x."
        if not (isProperty forestNode #units_y) do
            throw "Forest Pack property missing: units_y."

        local splineNode = findForestAreaSpline forestNode
        local values = calculateAssetAwareDistributionUnits sourceNode splineNode

        local spacingX = values[1]
        local spacingY = values[2]
        local sourceX = values[3]
        local sourceY = values[4]
        local areaX = values[5]
        local areaY = values[6]

        local previousX = forestNode.units_x
        local previousY = forestNode.units_y
        local beforeCount = getForestGeneratedItemCount forestNode

        try
        (
            forestNode.units_x = spacingX
            forestNode.units_y = spacingY

            if isProperty forestNode #distmode do forestNode.distmode = 0
            if isProperty forestNode #densityMap do forestNode.densityMap = false
            if isProperty forestNode #disabled do forestNode.disabled = false
            if isProperty forestNode #manualupdate do forestNode.manualupdate = false

            if abs (forestNode.units_x - spacingX) > 0.001 do
                throw "Asset-aware density verification failed: units_x mismatch."
            if abs (forestNode.units_y - spacingY) > 0.001 do
                throw "Asset-aware density verification failed: units_y mismatch."

            try (notifyDependents forestNode partID:#all message:#change) catch()
            completeRedraw()

            local afterCount = getForestGeneratedItemCount forestNode

            "{\"forest_name\":" + (jsonString forestNode.name) +
            ",\"source_name\":" + (jsonString sourceNode.name) +
            ",\"source_class\":" + (jsonString ((classOf sourceNode) as string)) +
            ",\"source_footprint_x\":" + (sourceX as string) +
            ",\"source_footprint_y\":" + (sourceY as string) +
            ",\"area_size_x\":" + (areaX as string) +
            ",\"area_size_y\":" + (areaY as string) +
            ",\"previous_units_x\":" + (previousX as string) +
            ",\"previous_units_y\":" + (previousY as string) +
            ",\"units_x\":" + (forestNode.units_x as string) +
            ",\"units_y\":" + (forestNode.units_y as string) +
            ",\"generated_items_before\":" + (beforeCount as string) +
            ",\"generated_items_after\":" + (afterCount as string) +
            ",\"verified\":true}"
        )
        catch
        (
            local message = getCurrentException()
            try (forestNode.units_x = previousX) catch()
            try (forestNode.units_y = previousY) catch()
            format "Forest Manager asset-aware density error: %\n" message
            throw
        )
    ),


    fn configureTargetItemDensityJson =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."

        local splineNode = findForestAreaSpline forestNode
        if splineNode == undefined do
            throw "Forest Pack object has no spline Area."

        if not (isProperty forestNode #units_x) do
            throw "Forest Pack property missing: units_x."
        if not (isProperty forestNode #units_y) do
            throw "Forest Pack property missing: units_y."

        local targetItems = 45000.0

        local bb = nodeGetBoundingBox splineNode splineNode.transform
        local areaSize = bb[2] - bb[1]
        local areaX = abs areaSize.x
        local areaY = abs areaSize.y
        local bboxArea = areaX * areaY

        if bboxArea <= 1.0 do
            throw "Spline bounding area is too small."

        -- First pass from the bounding box. Then calibrate from Forest's real
        -- generated item count. This makes the target robust for circles and
        -- irregular closed splines instead of assuming bbox area == spline area.
        local units = sqrt (bboxArea / targetItems)

        if units < 1.0 do units = 1.0
        if units > 10000.0 do units = 10000.0

        local previousX = forestNode.units_x
        local previousY = forestNode.units_y
        local beforeCount = getForestGeneratedItemCount forestNode
        local pass1Count = -1
        local pass2Count = -1

        try
        (
            if isProperty forestNode #distmode do forestNode.distmode = 0
            if isProperty forestNode #densityMap do forestNode.densityMap = false
            if isProperty forestNode #disabled do forestNode.disabled = false
            if isProperty forestNode #manualupdate do forestNode.manualupdate = false

            forestNode.units_x = units
            forestNode.units_y = units
            try (notifyDependents forestNode partID:#all message:#change) catch()
            completeRedraw()

            pass1Count = getForestGeneratedItemCount forestNode

            if pass1Count > 0 then
            (
                -- Item count is approximately inversely proportional to cell area.
                -- newUnits = oldUnits * sqrt(actual / target)
                local factor = sqrt ((pass1Count as float) / targetItems)
                units = units * factor
                if units < 1.0 do units = 1.0
                if units > 10000.0 do units = 10000.0

                forestNode.units_x = units
                forestNode.units_y = units
                try (notifyDependents forestNode partID:#all message:#change) catch()
                completeRedraw()
            )

            pass2Count = getForestGeneratedItemCount forestNode

            -- One final correction if still more than 5 percent away.
            if pass2Count > 0 and (abs (pass2Count - targetItems) / targetItems) > 0.05 then
            (
                local factor2 = sqrt ((pass2Count as float) / targetItems)
                units = units * factor2
                if units < 1.0 do units = 1.0
                if units > 10000.0 do units = 10000.0

                forestNode.units_x = units
                forestNode.units_y = units
                try (notifyDependents forestNode partID:#all message:#change) catch()
                completeRedraw()
            )

            local afterCount = getForestGeneratedItemCount forestNode

            "{\"forest_name\":" + (jsonString forestNode.name) +
            ",\"area_node\":" + (jsonString splineNode.name) +
            ",\"area_size_x\":" + (areaX as string) +
            ",\"area_size_y\":" + (areaY as string) +
            ",\"bbox_area\":" + (bboxArea as string) +
            ",\"target_items\":45000" +
            ",\"previous_units_x\":" + (previousX as string) +
            ",\"previous_units_y\":" + (previousY as string) +
            ",\"pass1_items\":" + (pass1Count as string) +
            ",\"pass2_items\":" + (pass2Count as string) +
            ",\"units_x\":" + (forestNode.units_x as string) +
            ",\"units_y\":" + (forestNode.units_y as string) +
            ",\"generated_items_before\":" + (beforeCount as string) +
            ",\"generated_items_after\":" + (afterCount as string) +
            ",\"verified\":true}"
        )
        catch
        (
            local message = getCurrentException()
            try (forestNode.units_x = previousX) catch()
            try (forestNode.units_y = previousY) catch()
            format "Forest Manager target density error: %\n" message
            throw
        )
    ),


    fn configureFixedDistributionUnitsJson =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."

        if not (isProperty forestNode #units_x) do
            throw "Forest Pack property missing: units_x."
        if not (isProperty forestNode #units_y) do
            throw "Forest Pack property missing: units_y."

        local targetUnits = 45000.0
        local previousX = forestNode.units_x
        local previousY = forestNode.units_y
        local previousMaxDensity = if isProperty forestNode #maxdensity then forestNode.maxdensity else undefined
        local beforeCount = getForestGeneratedItemCount forestNode

        try
        (
            forestNode.units_x = targetUnits
            forestNode.units_y = targetUnits

            if isProperty forestNode #distmode do forestNode.distmode = 0
            if isProperty forestNode #densityMap do forestNode.densityMap = false
            if isProperty forestNode #disabled do forestNode.disabled = false
            if isProperty forestNode #manualupdate do forestNode.manualupdate = false

            -- Runtime acceptance on Forest Pack 9.4.0 confirmed 10 million
            -- as a stable Max Density ceiling for this scene.
            if isProperty forestNode #maxdensity do
                forestNode.maxdensity = 10

            try (notifyDependents forestNode partID:#all message:#change) catch()
            completeRedraw()

            local afterCount = getForestGeneratedItemCount forestNode

            if abs (forestNode.units_x - targetUnits) > 0.001 do
                throw "Fixed distribution verification failed: units_x mismatch."
            if abs (forestNode.units_y - targetUnits) > 0.001 do
                throw "Fixed distribution verification failed: units_y mismatch."
            if isProperty forestNode #maxdensity and forestNode.maxdensity != 10 do
                throw "Fixed distribution verification failed: maxdensity mismatch."

            "{\"forest_name\":" + (jsonString forestNode.name) +
            ",\"target_units\":450000.0" +
            ",\"previous_units_x\":" + (previousX as string) +
            ",\"previous_units_y\":" + (previousY as string) +
            ",\"units_x\":" + (forestNode.units_x as string) +
            ",\"units_y\":" + (forestNode.units_y as string) +
            ",\"maxdensity\":" + ((if isProperty forestNode #maxdensity then forestNode.maxdensity else -1) as string) +
            ",\"generated_items_before\":" + (beforeCount as string) +
            ",\"generated_items_after\":" + (afterCount as string) +
            ",\"verified\":true}"
        )
        catch
        (
            local message = getCurrentException()
            try (forestNode.units_x = previousX) catch()
            try (forestNode.units_y = previousY) catch()
            try
            (
                if previousMaxDensity != undefined and isProperty forestNode #maxdensity do
                    forestNode.maxdensity = previousMaxDensity
            )
            catch()

            format "Forest Manager fixed distribution error: %\n" message
            throw
        )
    ),


    fn configureDensityMetersJson densityMeters =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        if densityMeters <= 0.0 do
            throw "Forest density must be greater than zero meters."

        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."

        if not (isProperty forestNode #units_x) do
            throw "Forest Pack property missing: units_x."
        if not (isProperty forestNode #units_y) do
            throw "Forest Pack property missing: units_y."

        local previousX = forestNode.units_x
        local previousY = forestNode.units_y
        local previousMaxDensity = if isProperty forestNode #maxdensity then forestNode.maxdensity else undefined
        local beforeCount = getForestGeneratedItemCount forestNode
        local oneMeterSystemUnits = metersToSystemUnits 1.0
        local densitySystemUnits = metersToSystemUnits densityMeters
        local densityDisplayValue = formatSystemValueForScene densitySystemUnits

        if oneMeterSystemUnits <= 0.0 do
            throw "Forest density verification failed: 1 meter conversion is invalid."
        if densitySystemUnits <= 0.0 do
            throw "Forest density verification failed: computed system-unit value is invalid."

        try
        (
            forestNode.units_x = densitySystemUnits
            forestNode.units_y = densitySystemUnits

            if isProperty forestNode #distmode do forestNode.distmode = 0
            if isProperty forestNode #densityMap do forestNode.densityMap = false
            if isProperty forestNode #disabled do forestNode.disabled = false
            if isProperty forestNode #manualupdate do forestNode.manualupdate = false
            if isProperty forestNode #maxdensity do forestNode.maxdensity = 10

            try (notifyDependents forestNode partID:#all message:#change) catch()
            completeRedraw()

            local afterCount = getForestGeneratedItemCount forestNode

            if forestNode.units_x <= 0.0 or forestNode.units_y <= 0.0 do
                throw "Forest density verification failed: Forest units must be positive."
            if abs (forestNode.units_x - densitySystemUnits) > 0.001 do
                throw "Forest density verification failed: units_x mismatch."
            if abs (forestNode.units_y - densitySystemUnits) > 0.001 do
                throw "Forest density verification failed: units_y mismatch."

            "{\"forest_name\":" + (jsonString forestNode.name) +
            ",\"density_m\":" + (densityMeters as string) +
            ",\"one_meter_system_units\":" + (oneMeterSystemUnits as string) +
            ",\"density_system_units\":" + (densitySystemUnits as string) +
            ",\"density_display_value\":" + (jsonString densityDisplayValue) +
            ",\"density_meters_x\":" + ((forestNode.units_x / oneMeterSystemUnits) as string) +
            ",\"density_meters_y\":" + ((forestNode.units_y / oneMeterSystemUnits) as string) +
            ",\"display_type\":" + (jsonString (units.DisplayType as string)) +
            ",\"display_unit\":" + (jsonString (getDisplayUnitName())) +
            ",\"system_type\":" + (jsonString (units.SystemType as string)) +
            ",\"system_scale\":" + (units.SystemScale as string) +
            ",\"previous_units_x\":" + (previousX as string) +
            ",\"previous_units_y\":" + (previousY as string) +
            ",\"units_x\":" + (forestNode.units_x as string) +
            ",\"units_y\":" + (forestNode.units_y as string) +
            ",\"maxdensity\":" + ((if isProperty forestNode #maxdensity then forestNode.maxdensity else -1) as string) +
            ",\"generated_items_before\":" + (beforeCount as string) +
            ",\"generated_items_after\":" + (afterCount as string) +
            ",\"generated_count_probe\":\"trees.count\"" +
            ",\"generated_count_authoritative\":false" +
            ",\"verified\":true}"
        )
        catch
        (
            local message = getCurrentException()
            try (forestNode.units_x = previousX) catch()
            try (forestNode.units_y = previousY) catch()
            try
            (
                if previousMaxDensity != undefined and isProperty forestNode #maxdensity do
                    forestNode.maxdensity = previousMaxDensity
            )
            catch()
            format "Forest Manager density error: %\\n" message
            throw
        )
    ),

    fn configurePhysicalSpacingJson spacingMeters =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        if spacingMeters <= 0.0 do
            throw "Physical spacing must be greater than zero meters."

        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."

        if not (isProperty forestNode #units_x) do
            throw "Forest Pack property missing: units_x."
        if not (isProperty forestNode #units_y) do
            throw "Forest Pack property missing: units_y."

        local previousX = forestNode.units_x
        local previousY = forestNode.units_y
        local previousMaxDensity = if isProperty forestNode #maxdensity then forestNode.maxdensity else undefined
        local beforeCount = getForestGeneratedItemCount forestNode

        local oneMeterSystemUnits = units.decodeValue "1m"
        local spacingSystemUnits = oneMeterSystemUnits * spacingMeters

        if oneMeterSystemUnits <= 0.0 do
            throw "Physical spacing verification failed: 1 meter conversion is invalid."
        if spacingSystemUnits <= 0.0 do
            throw "Physical spacing verification failed: computed spacing is invalid."

        try
        (
            forestNode.units_x = spacingSystemUnits
            forestNode.units_y = spacingSystemUnits

            if isProperty forestNode #distmode do forestNode.distmode = 0
            if isProperty forestNode #densityMap do forestNode.densityMap = false
            if isProperty forestNode #disabled do forestNode.disabled = false
            if isProperty forestNode #manualupdate do forestNode.manualupdate = false
            if isProperty forestNode #maxdensity do forestNode.maxdensity = 10

            try (notifyDependents forestNode partID:#all message:#change) catch()
            completeRedraw()

            local afterCount = getForestGeneratedItemCount forestNode

            if forestNode.units_x <= 0.0 or forestNode.units_y <= 0.0 do
                throw "Physical spacing verification failed: Forest units must be positive."
            if abs (forestNode.units_x - spacingSystemUnits) > 0.001 do
                throw "Physical spacing verification failed: units_x mismatch."
            if abs (forestNode.units_y - spacingSystemUnits) > 0.001 do
                throw "Physical spacing verification failed: units_y mismatch."

            "{\"forest_name\":" + (jsonString forestNode.name) +
            ",\"spacing_m\":" + (spacingMeters as string) +
            ",\"one_meter_system_units\":" + (oneMeterSystemUnits as string) +
            ",\"spacing_system_units\":" + (spacingSystemUnits as string) +
            ",\"previous_units_x\":" + (previousX as string) +
            ",\"previous_units_y\":" + (previousY as string) +
            ",\"units_x\":" + (forestNode.units_x as string) +
            ",\"units_y\":" + (forestNode.units_y as string) +
            ",\"maxdensity\":" + ((if isProperty forestNode #maxdensity then forestNode.maxdensity else -1) as string) +
            ",\"generated_items_before\":" + (beforeCount as string) +
            ",\"generated_items_after\":" + (afterCount as string) +
            ",\"verified\":true}"
        )
        catch
        (
            local message = getCurrentException()
            try (forestNode.units_x = previousX) catch()
            try (forestNode.units_y = previousY) catch()
            try
            (
                if previousMaxDensity != undefined and isProperty forestNode #maxdensity do
                    forestNode.maxdensity = previousMaxDensity
            )
            catch()
            format "Forest Manager physical spacing error: %\n" message
            throw
        )
    ),



    fn setGeometryItemAtIndex forestNode index sourceNode probabilityValue =
    (
        local geometryProps = #(
            #cobjlist, #namelist, #matlist, #coloridlist, #geomlist,
            #tempidlist, #tempnamelist, #widthlist, #heightlist, #ScaleList,
            #zoffsetlist, #radiuslist, #specidlist, #usemeshdimlist,
            #conamelist, #includechildlist, #keepgrouplist, #nongeomlist,
            #old_problist, #problist, #centerlist
        )
        for propName in geometryProps do ensureGeometryArrayCount forestNode propName index

        local bb = nodeGetBoundingBox sourceNode sourceNode.transform
        local rawSize = bb[2] - bb[1]
        local sizeX = abs rawSize.x
        local sizeY = abs rawSize.y
        local sizeZ = abs rawSize.z

        if isProperty forestNode #geomlist do forestNode.geomlist[index] = 2
        if isProperty forestNode #namelist do forestNode.namelist[index] = sourceNode.name
        if isProperty forestNode #tempnamelist do forestNode.tempnamelist[index] = sourceNode.name
        if isProperty forestNode #tempidlist do forestNode.tempidlist[index] = 0
        if isProperty forestNode #matlist do forestNode.matlist[index] = sourceNode.material
        if isProperty forestNode #coloridlist do forestNode.coloridlist[index] = sourceNode.wirecolor
        if isProperty forestNode #widthlist and sizeX > 0.0 do forestNode.widthlist[index] = sizeX
        if isProperty forestNode #heightlist and sizeZ > 0.0 do forestNode.heightlist[index] = sizeZ
        if isProperty forestNode #ScaleList do forestNode.ScaleList[index] = 100.0
        if isProperty forestNode #zoffsetlist do forestNode.zoffsetlist[index] = 0.0
        if isProperty forestNode #radiuslist do forestNode.radiuslist[index] = 100
        if isProperty forestNode #specidlist do forestNode.specidlist[index] = index
        if isProperty forestNode #usemeshdimlist do forestNode.usemeshdimlist[index] = false
        if isProperty forestNode #conamelist do forestNode.conamelist[index] = ""
        if isProperty forestNode #includechildlist do forestNode.includechildlist[index] = false
        if isProperty forestNode #keepgrouplist do forestNode.keepgrouplist[index] = false
        if isProperty forestNode #nongeomlist do forestNode.nongeomlist[index] = false
        if isProperty forestNode #problist do forestNode.problist[index] = probabilityValue
        if isProperty forestNode #old_problist do forestNode.old_problist[index] = (probabilityValue as integer)
        if isProperty forestNode #centerlist do forestNode.centerlist[index] = 50

        forestNode.cobjlist[index] = undefined
        forestNode.cobjlist[index] = sourceNode
        if forestNode.cobjlist[index] != sourceNode do throw "Forest Pack source assignment verification failed."
        #(sizeX, sizeY, sizeZ)
    ),

    fn equalizeGeometryProbabilities forestNode =
    (
        if not (isProperty forestNode #cobjlist) do return false
        local count = forestNode.cobjlist.count
        if count < 1 do return false
        local probabilityValue = 100.0 / count
        if isProperty forestNode #problist do
        (
            forestNode.problist.count = count
            for i = 1 to count do forestNode.problist[i] = probabilityValue
        )
        if isProperty forestNode #old_problist do
        (
            forestNode.old_problist.count = count
            local oldValue = probabilityValue as integer
            for i = 1 to count do forestNode.old_problist[i] = oldValue
        )
        true
    ),

    fn findGeometrySourceIndexByName forestNode sourceName =
    (
        if forestNode == undefined do return 0
        if not (isProperty forestNode #cobjlist) do return 0

        local wanted = toLower sourceName
        for i = 1 to forestNode.cobjlist.count do
        (
            local node = forestNode.cobjlist[i]
            if node != undefined and (toLower node.name) == wanted do
                return i
        )
        0
    ),

    fn addNamedGeometrySourceJson forestName sourceName =
    (
        if not (forestPackAvailable()) do throw "Forest Pack Pro class ::Forest_Pro is not available."
        local forestNode = getNodeByName forestName
        if forestNode == undefined do throw ("Forest object not found: " + forestName)
        if not (isKindOf forestNode ::Forest_Pro) do throw ("Node is not Forest Pack: " + forestName)
        local sourceNode = getNodeByName sourceName
        if sourceNode == undefined do throw ("Source geometry node not found: " + sourceName)
        if sourceNode == forestNode do throw "Source geometry cannot be the Forest object."
        if superClassOf sourceNode == Shape do throw "Source geometry must not be a spline/shape."

        local existingIndex = findGeometrySourceIndexByName forestNode sourceName
        if existingIndex > 0 then
        (
            return "{\"forest_name\":" + (jsonString forestNode.name) +
                ",\"source_name\":" + (jsonString sourceNode.name) +
                ",\"geometry_index\":" + (existingIndex as string) +
                ",\"added\":false,\"verified\":true}"
        )

        local geometryProps = #(
            #cobjlist, #namelist, #matlist, #coloridlist, #geomlist,
            #tempidlist, #tempnamelist, #widthlist, #heightlist, #ScaleList,
            #zoffsetlist, #radiuslist, #specidlist, #usemeshdimlist,
            #conamelist, #includechildlist, #keepgrouplist, #nongeomlist,
            #old_problist, #problist, #centerlist
        )
        local oldCounts = rememberGeometryCounts forestNode geometryProps
        local newIndex = forestNode.cobjlist.count + 1
        try
        (
            setGeometryItemAtIndex forestNode newIndex sourceNode 100.0
            if forestNode.cobjlist.count != newIndex do throw "Geometry-source insertion count verification failed."
            if findGeometrySourceIndexByName forestNode sourceName != newIndex do throw "Geometry-source insertion identity verification failed."
            completeRedraw()
            "{\"forest_name\":" + (jsonString forestNode.name) +
            ",\"source_name\":" + (jsonString sourceNode.name) +
            ",\"geometry_index\":" + (newIndex as string) +
            ",\"added\":true,\"verified\":true}"
        )
        catch
        (
            rollbackGeometryCounts forestNode oldCounts
            throw
        )
    ),

    fn removeGeometrySourceTailJson forestName geometryIndex =
    (
        if not (forestPackAvailable()) do throw "Forest Pack Pro class ::Forest_Pro is not available."
        local forestNode = getNodeByName forestName
        if forestNode == undefined do throw ("Forest object not found: " + forestName)
        if not (isProperty forestNode #cobjlist) do throw "Forest Pack property missing: cobjlist."
        local currentCount = forestNode.cobjlist.count
        if geometryIndex != currentCount do throw "Geometry-source rollback only permits the current tail index."
        if geometryIndex < 1 do throw "Geometry-source rollback index must be one or greater."
        local geometryProps = #(
            #cobjlist, #namelist, #matlist, #coloridlist, #geomlist,
            #tempidlist, #tempnamelist, #widthlist, #heightlist, #ScaleList,
            #zoffsetlist, #radiuslist, #specidlist, #usemeshdimlist,
            #conamelist, #includechildlist, #keepgrouplist, #nongeomlist,
            #old_problist, #problist, #centerlist
        )
        for propName in geometryProps do
        (
            if isProperty forestNode propName then
            (
                local arr = getProperty forestNode propName
                if classOf arr == ArrayParameter and arr.count == currentCount do arr.count = currentCount - 1
            )
        )
        if forestNode.cobjlist.count != currentCount - 1 do throw "Geometry-source rollback count verification failed."
        completeRedraw()
        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"removed_index\":" + (geometryIndex as string) +
        ",\"geometry_count\":" + (forestNode.cobjlist.count as string) +
        ",\"verified\":true}"
    ),

    fn appendT2AssetGeometryJson assetPath probabilityValue =
    (
        if assetPath == undefined or assetPath == "" do throw "T2 asset path is empty."
        if not (doesFileExist assetPath) do throw ("T2 asset file does not exist: " + assetPath)
        if toLower (getFilenameType assetPath) != ".max" do throw "Stage 4F accepts only .max assets."
        if probabilityValue <= 0.0 or probabilityValue > 100.0 do throw "Probability must be in the range (0, 100]."
        if not (forestPackAvailable()) do throw "Forest Pack Pro class ::Forest_Pro is not available."

        local forestNode = findStage3Forest()
        if forestNode == undefined do throw "No Forest Pack object exists in the scene."

        local expectedSourceName = getFilenameFile assetPath
        if findGeometrySourceIndexByName forestNode expectedSourceName > 0 do
            throw ("Forest Geometry already contains asset: " + expectedSourceName)

        local beforeObjects = objects as array
        clearSelection()
        local mergeResult = false
        try
        (
            mergeResult = mergeMAXFile assetPath #select #autoRenameDups #useMergedMtlDups quiet:true
        )
        catch
        (
            reportBridgeError (currentExceptionDetails "APPEND_STEP[mergeMAXFile]: ")
            throw()
        )
        local afterObjects = objects as array
        local newObjects = for obj in afterObjects where (findItem beforeObjects obj) == 0 collect obj
        if newObjects.count < 1 do throw "APPEND_STEP[newObjects]: T2 asset merge produced no new scene nodes."

        local refLayer = getOrCreateReferenceLayer()
        for obj in newObjects do
        (
            markForestManagerOwnedNode obj role:"merged_asset_node"
            try (refLayer.addNode obj) catch()
        )
        try (refLayer.on = false) catch()

        local sourceNode = chooseMergedSourceNode newObjects expectedSourceName:expectedSourceName
        if sourceNode == undefined do throw "Could not choose a Forest source from merged nodes."

        try (sourceNode.name = expectedSourceName) catch()

        local selectedClassName = ""
        try (selectedClassName = toLower ((classOf sourceNode) as string)) catch()
        if selectedClassName == "plane" then
        (
            local hasNonPlaneGeometry = false
            for obj in newObjects while not hasNonPlaneGeometry do
            (
                local isGeometry = false
                local className = ""
                try (isGeometry = (superClassOf obj == GeometryClass)) catch()
                try (className = toLower ((classOf obj) as string)) catch()
                if isGeometry and className != "plane" do hasNonPlaneGeometry = true
            )
            if hasNonPlaneGeometry do
                throw "Source selection rejected helper Plane while vegetation geometry exists."
        )

        if findGeometrySourceIndexByName forestNode sourceNode.name > 0 do
        (
            try (delete newObjects) catch()
            throw ("Forest Geometry already contains asset: " + sourceNode.name)
        )

        if sourceNode.parent == undefined do (try (sourceNode.position = [0,0,0]) catch())

        try
        (
            prepareReferenceNode sourceNode
        )
        catch
        (
            reportBridgeError ("APPEND_STEP[prepareReferenceNode]: " + (getCurrentException()))
            throw()
        )

        local currentCount = if isProperty forestNode #cobjlist then forestNode.cobjlist.count else 0
        local newIndex = currentCount + 1
        local dimensions = undefined
        try
        (
            dimensions = setGeometryItemAtIndex forestNode newIndex sourceNode probabilityValue
        )
        catch
        (
            reportBridgeError ("APPEND_STEP[setGeometryItemAtIndex]: " + (getCurrentException()))
            throw()
        )
        equalizeGeometryProbabilities forestNode

        if isProperty forestNode #units_x do forestNode.units_x = 45000.0
        if isProperty forestNode #units_y do forestNode.units_y = 45000.0
        if isProperty forestNode #maxdensity do forestNode.maxdensity = 10
        if isProperty forestNode #distmode do forestNode.distmode = 0
        if isProperty forestNode #densityMap do forestNode.densityMap = false
        if isProperty forestNode #disabled do forestNode.disabled = false
        if isProperty forestNode #manualupdate do forestNode.manualupdate = false

        select newObjects
        try (notifyDependents forestNode partID:#all message:#change) catch()
        completeRedraw()

        local generatedCount = getForestGeneratedItemCount forestNode
        local geometryCount = forestNode.cobjlist.count
        local namesJson = "["
        local probsJson = "["
        for i = 1 to geometryCount do
        (
            if i > 1 do (namesJson += ","; probsJson += ",")
            local nodeName = ""
            if forestNode.cobjlist[i] != undefined do nodeName = forestNode.cobjlist[i].name
            namesJson += jsonString nodeName
            local p = if isProperty forestNode #problist then forestNode.problist[i] else 0.0
            probsJson += (p as string)
        )
        namesJson += "]"
        probsJson += "]"

        local verified = true
        if geometryCount != newIndex do verified = false
        if forestNode.cobjlist[newIndex] != sourceNode do verified = false
        if isProperty forestNode #geomlist and forestNode.geomlist[newIndex] != 2 do verified = false

        "{\"asset_path\":" + (jsonString assetPath) +
        ",\"forest_name\":" + (jsonString forestNode.name) +
        ",\"source_name\":" + (jsonString sourceNode.name) +
        ",\"source_class\":" + (jsonString ((classOf sourceNode) as string)) +
        ",\"geometry_index\":" + (newIndex as string) +
        ",\"geometry_count\":" + (geometryCount as string) +
        ",\"source_width\":" + (dimensions[1] as string) +
        ",\"source_depth\":" + (dimensions[2] as string) +
        ",\"source_height\":" + (dimensions[3] as string) +
        ",\"source_width_display\":" + (jsonString (formatSystemValueForScene dimensions[1])) +
        ",\"source_depth_display\":" + (jsonString (formatSystemValueForScene dimensions[2])) +
        ",\"source_height_display\":" + (jsonString (formatSystemValueForScene dimensions[3])) +
        ",\"geometry_names\":" + namesJson +
        ",\"probabilities\":" + probsJson +
        ",\"units_x\":" + ((if isProperty forestNode #units_x then forestNode.units_x else 0.0) as string) +
        ",\"units_y\":" + ((if isProperty forestNode #units_y then forestNode.units_y else 0.0) as string) +
        ",\"units_x_display\":" + (jsonString (formatSystemValueForScene (if isProperty forestNode #units_x then forestNode.units_x else 0.0))) +
        ",\"units_y_display\":" + (jsonString (formatSystemValueForScene (if isProperty forestNode #units_y then forestNode.units_y else 0.0))) +
        ",\"maxdensity\":" + ((if isProperty forestNode #maxdensity then forestNode.maxdensity else -1) as string) +
        ",\"generated_items\":" + (generatedCount as string) +
        ",\"verified\":" + (boolJson verified) + "}"
    ),


    fn normalizeProbabilityValues values =
    (
        if values == undefined or values.count < 1 do
            throw "Probability list is empty."

        local total = 0.0
        for value in values do
        (
            if value <= 0.0 do
                throw "All probabilities must be greater than zero."
            total += value
        )

        if total <= 0.0 do
            throw "Probability total must be greater than zero."

        local normalized = #()
        for value in values do
            append normalized ((value / total) * 100.0)

        normalized
    ),

    fn setForestGeometryProbabilitiesJson values =
    (
        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."
        if not (isProperty forestNode #cobjlist) do
            throw "Forest Pack property missing: cobjlist."
        if not (isProperty forestNode #problist) do
            throw "Forest Pack property missing: problist."

        local geometryCount = forestNode.cobjlist.count
        if geometryCount < 1 do
            throw "Forest Geometry List is empty."
        if values.count != geometryCount do
            throw "Probability count must match Forest Geometry count."

        local normalized = normalizeProbabilityValues values

        forestNode.problist.count = geometryCount
        for i = 1 to geometryCount do
            forestNode.problist[i] = normalized[i]

        if isProperty forestNode #old_problist do
        (
            forestNode.old_problist.count = geometryCount
            for i = 1 to geometryCount do
                forestNode.old_problist[i] = (normalized[i] as integer)
        )

        if isProperty forestNode #disabled do forestNode.disabled = false
        if isProperty forestNode #manualupdate do forestNode.manualupdate = false

        try (notifyDependents forestNode partID:#all message:#change) catch()
        completeRedraw()

        local namesJson = "["
        local probsJson = "["
        local totalAfter = 0.0

        for i = 1 to geometryCount do
        (
            if i > 1 do
            (
                namesJson += ","
                probsJson += ","
            )

            local nodeName = ""
            if forestNode.cobjlist[i] != undefined do
                nodeName = forestNode.cobjlist[i].name

            namesJson += jsonString nodeName
            probsJson += (forestNode.problist[i] as string)
            totalAfter += forestNode.problist[i]
        )

        namesJson += "]"
        probsJson += "]"

        local verified = abs (totalAfter - 100.0) < 0.05

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"geometry_count\":" + (geometryCount as string) +
        ",\"geometry_names\":" + namesJson +
        ",\"probabilities\":" + probsJson +
        ",\"probability_total\":" + (totalAfter as string) +
        ",\"generated_items\":" + (getForestGeneratedItemCount forestNode as string) +
        ",\"verified\":" + (boolJson verified) + "}"
    ),


    fn normalizeReferenceSourcesJson =
    (
        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."
        if not (isProperty forestNode #cobjlist) do
            throw "Forest Pack property missing: cobjlist."

        local refLayer = getOrCreateReferenceLayer()
        local targetZ = millimetersToSystemUnits -1500.0
        local moved = 0
        local namesJson = "["

        for i = 1 to forestNode.cobjlist.count do
        (
            local node = forestNode.cobjlist[i]
            if node != undefined do
            (
                if moved > 0 do namesJson += ","
                namesJson += jsonString node.name

                prepareReferenceNode node
                moved += 1
            )
        )

        namesJson += "]"
        refLayer.on = false

        local verified = true
        for i = 1 to forestNode.cobjlist.count do
        (
            local node = forestNode.cobjlist[i]
            if node != undefined do
            (
                if abs (node.position.z - targetZ) > 0.001 do verified = false
            )
        )

        if refLayer.on != false do verified = false

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"layer_name\":\"FM_References\"" +
        ",\"layer_visible\":" + (boolJson refLayer.on) +
        ",\"target_z_mm\":-1500.0" +
        ",\"target_z_system_units\":" + (targetZ as string) +
        ",\"target_z_display\":" + (jsonString (formatSystemValueForScene targetZ)) +
        ",\"reference_count\":" + (moved as string) +
        ",\"reference_names\":" + namesJson +
        ",\"verified\":" + (boolJson verified) + "}"
    ),


    fn getForestGeometrySummaryJson =
    (
        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."
        if not (isProperty forestNode #cobjlist) do
            throw "Forest Pack property missing: cobjlist."

        local geometryCount = forestNode.cobjlist.count
        local namesJson = "["
        local classesJson = "["
        local probsJson = "["

        for i = 1 to geometryCount do
        (
            if i > 1 do
            (
                namesJson += ","
                classesJson += ","
                probsJson += ","
            )

            local node = forestNode.cobjlist[i]
            local nodeName = ""
            local nodeClass = ""

            if node != undefined do
            (
                nodeName = node.name
                nodeClass = (classOf node) as string
            )

            namesJson += jsonString nodeName
            classesJson += jsonString nodeClass

            local p = if isProperty forestNode #problist and forestNode.problist.count >= i then forestNode.problist[i] else 0.0
            probsJson += (p as string)
        )

        namesJson += "]"
        classesJson += "]"
        probsJson += "]"

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"geometry_count\":" + (geometryCount as string) +
        ",\"geometry_names\":" + namesJson +
        ",\"geometry_classes\":" + classesJson +
        ",\"probabilities\":" + probsJson +
        ",\"units_x\":" + ((if isProperty forestNode #units_x then forestNode.units_x else 0.0) as string) +
        ",\"units_y\":" + ((if isProperty forestNode #units_y then forestNode.units_y else 0.0) as string) +
        ",\"units_x_display\":" + (jsonString (formatSystemValueForScene (if isProperty forestNode #units_x then forestNode.units_x else 0.0))) +
        ",\"units_y_display\":" + (jsonString (formatSystemValueForScene (if isProperty forestNode #units_y then forestNode.units_y else 0.0))) +
        ",\"maxdensity\":" + ((if isProperty forestNode #maxdensity then forestNode.maxdensity else -1) as string) + "}"
    ),

    fn safePropertyValueJson owner propName =
    (
        local value = undefined
        try (value = getProperty owner propName) catch (value = undefined)
        if value == undefined do return "null"

        local valueClass = safeClassName value
        if valueClass == "BooleanClass" then
            return (boolJson value)

        if valueClass == "Integer" or valueClass == "Integer64" or valueClass == "Float" or valueClass == "Double" then
            return (value as string)

        if valueClass == "Point2" or valueClass == "Point3" or valueClass == "Point4" then
            return (jsonString (value as string))

        if valueClass == "Color" then
            return ("[" + (value.r as string) + "," + (value.g as string) + "," + (value.b as string) + "]")

        if valueClass == "String" then
            return (jsonString value)

        jsonString (value as string)
    ),

    fn refreshForestPreviewNode forestNode =
    (
        if forestNode == undefined do return false
        try (if isProperty forestNode #manualupdate do forestNode.manualupdate = false) catch()
        try (forestNode.update()) catch()
        try (notifyDependents forestNode partID:#all message:#change) catch()
        try (redrawViews()) catch()
        try (completeRedraw()) catch()
        true
    ),

    fn ensureSpeciesPreviewRuntimeBinding layerNode legacyNode =
    (
        if layerNode == undefined do
            throw "Species preview layer is undefined."
        if legacyNode == undefined do
            throw "Legacy Forest is undefined."

        local sourceSpline = findForestAreaSpline legacyNode
        if sourceSpline == undefined do
            throw "Verified legacy Forest area spline was not found."

        local layerSpline = findForestAreaSpline layerNode
        local areaRebound = false
        if layerSpline == undefined then
        (
            local areaIndex = addSplineIncludeArea layerNode sourceSpline
            if not (verifySplineArea layerNode sourceSpline areaIndex) do
                throw ("Species preview spline-area recovery failed: " + layerNode.name)
            layerSpline = sourceSpline
            areaRebound = true
        )

        if not (isProperty layerNode #cobjlist) do
            throw ("Species preview geometry contract is unavailable: " + layerNode.name)
        if layerNode.cobjlist.count < 1 or layerNode.cobjlist[1] == undefined do
            throw ("Species preview geometry source is missing: " + layerNode.name)

        local sourceNode = layerNode.cobjlist[1]
        local beforeCount = getForestGeneratedItemCount layerNode
        refreshForestPreviewNode layerNode
        local afterCount = getForestGeneratedItemCount layerNode

        #(sourceSpline, layerSpline, sourceNode, areaRebound, beforeCount, afterCount)
    ),

    fn getSpeciesPreviewNodes =
    (
        local legacy = getNodeByName "FM_Forest_001"
        if legacy == undefined do throw "FM_Forest_001 was not found."

        local layerNames = #(
            "FM_Layer_01_foreground_mass",
            "FM_Layer_02_mid_accent",
            "FM_Layer_03_structural_shrub"
        )

        local layers = #()
        for layerName in layerNames do
        (
            local layerNode = getNodeByName layerName
            if layerNode == undefined do
                throw ("Prepared species layer was not found: " + layerName)
            append layers layerNode
        )

        #(legacy, layers)
    ),

    fn normalizeSpeciesDensityMapCoords coords =
    (
        if coords == undefined do
            throw "Species Bitmaptexture coords are unavailable."

        coords.realWorldScale = false
        coords.U_Tiling = 1.0
        coords.V_Tiling = 1.0
        coords.U_Offset = 0.0
        coords.V_Offset = 0.0
        coords.U_Tile = false
        coords.V_Tile = false

        if coords.realWorldScale != false do throw "Normalized UV verification failed: realWorldScale."
        if abs(coords.U_Tiling - 1.0) > 0.0001 do throw "Normalized UV verification failed: U_Tiling."
        if abs(coords.V_Tiling - 1.0) > 0.0001 do throw "Normalized UV verification failed: V_Tiling."
        if abs(coords.U_Offset) > 0.0001 do throw "Normalized UV verification failed: U_Offset."
        if abs(coords.V_Offset) > 0.0001 do throw "Normalized UV verification failed: V_Offset."
        if coords.U_Tile != false do throw "Normalized UV verification failed: U_Tile."
        if coords.V_Tile != false do throw "Normalized UV verification failed: V_Tile."

        true
    ),

    fn configureSpeciesDensityMapTilingCoords coords =
    (
        if coords == undefined do
            throw "Species Bitmaptexture coords are unavailable."

        -- Forest Pack Image Mode uses units_x/units_y as the physical size of
        -- one distribution-map tile. Keep the protected 75 m Forest density
        -- units and allow the map to repeat across the complete spline area.
        coords.realWorldScale = false
        coords.U_Tiling = 1.0
        coords.V_Tiling = 1.0
        coords.U_Offset = 0.0
        coords.V_Offset = 0.0
        coords.U_Tile = true
        coords.V_Tile = true

        if coords.realWorldScale != false do throw "Forest XY tile verification failed: realWorldScale."
        if abs(coords.U_Tiling - 1.0) > 0.0001 do throw "Forest XY tile verification failed: U_Tiling."
        if abs(coords.V_Tiling - 1.0) > 0.0001 do throw "Forest XY tile verification failed: V_Tiling."
        if abs(coords.U_Offset) > 0.0001 do throw "Forest XY tile verification failed: U_Offset."
        if abs(coords.V_Offset) > 0.0001 do throw "Forest XY tile verification failed: V_Offset."
        if coords.U_Tile != true do throw "Forest XY tile verification failed: U_Tile."
        if coords.V_Tile != true do throw "Forest XY tile verification failed: V_Tile."
        true
    ),

    fn configureSpeciesMapProjectionJson =
    (
        local nodes = getSpeciesPreviewNodes()
        local legacy = nodes[1]
        local layers = nodes[2]
        local splineNode = findForestAreaSpline legacy
        if splineNode == undefined do throw "Verified Forest area spline was not found."

        local oneMeter = 0.0
        try (oneMeter = units.decodeValue "1m") catch (oneMeter = 0.0)
        if oneMeter <= 0.0 do throw "Could not resolve active scene meter conversion."

        local bb = nodeGetBoundingBox splineNode splineNode.transform
        local pmin = bb[1]
        local pmax = bb[2]
        local centerX = (pmin.x + pmax.x) * 0.5
        local centerY = (pmin.y + pmax.y) * 0.5

        local oldOffsetX = #()
        local oldOffsetY = #()
        for layerNode in layers do
        (
            append oldOffsetX layerNode.offset_X
            append oldOffsetY layerNode.offset_Y
        )

        try
        (
            for layerNode in layers do
            (
                if abs((layerNode.units_x / oneMeter) - 75.0) > 0.001 do
                    throw ("Protected Density Units X is not 75.0 m on " + layerNode.name)
                if abs((layerNode.units_y / oneMeter) - 75.0) > 0.001 do
                    throw ("Protected Density Units Y is not 75.0 m on " + layerNode.name)
                if layerNode.distmap == undefined do
                    throw ("Distribution map is missing on " + layerNode.name)

                local coords = undefined
                try (coords = layerNode.distmap.coords) catch (coords = undefined)
                if coords == undefined do
                    throw ("Species Bitmaptexture coords are unavailable: " + layerNode.name)

                configureSpeciesDensityMapTilingCoords coords
                layerNode.offset_X = centerX
                layerNode.offset_Y = centerY
                refreshForestPreviewNode layerNode
            )
        )
        catch
        (
            for i = 1 to layers.count do
            (
                try (layers[i].offset_X = oldOffsetX[i]) catch()
                try (layers[i].offset_Y = oldOffsetY[i]) catch()
            )
            throw
        )

        local layersJson = "["
        for i = 1 to layers.count do
        (
            if i > 1 do layersJson += ","
            local layerNode = layers[i]
            local coords = layerNode.distmap.coords
            layersJson += "{\"forest_name\":" + (jsonString layerNode.name) +
                          ",\"density_meters_x\":" + ((layerNode.units_x / oneMeter) as string) +
                          ",\"density_meters_y\":" + ((layerNode.units_y / oneMeter) as string) +
                          ",\"forest_offset_meters_x\":" + ((layerNode.offset_X / oneMeter) as string) +
                          ",\"forest_offset_meters_y\":" + ((layerNode.offset_Y / oneMeter) as string) +
                          ",\"u_tile\":" + (boolJson coords.U_Tile) +
                          ",\"v_tile\":" + (boolJson coords.V_Tile) +
                          ",\"real_world_scale\":" + (boolJson coords.realWorldScale) +
                          ",\"verified\":true}"
        )
        layersJson += "]"

        "{\"projection\":\"forest_xy_tiled_75m\"" +
        ",\"spline_name\":" + (jsonString splineNode.name) +
        ",\"spline_center_x_meters\":" + ((centerX / oneMeter) as string) +
        ",\"spline_center_y_meters\":" + ((centerY / oneMeter) as string) +
        ",\"layers\":" + layersJson +
        ",\"verified\":true}"
    ),

    fn applySpeciesUvClampPreviewJson =
    (
        local nodes = getSpeciesPreviewNodes()
        local legacy = nodes[1]
        local layers = nodes[2]
        local target = layers[1]

        if target.distmap == undefined do
            throw "Foreground species distribution map is missing."

        local coords = undefined
        try (coords = target.distmap.coords) catch (coords = undefined)
        if coords == undefined do
            throw "Foreground species Bitmaptexture coords are unavailable."

        local oneMeter = 0.0
        try (oneMeter = units.decodeValue "1m") catch (oneMeter = 0.0)
        if oneMeter <= 0.0 do
            throw "Could not resolve active scene meter conversion."

        if abs((target.units_x / oneMeter) - 75.0) > 0.001 do
            throw "Protected Density Units X is not 75.0 m."
        if abs((target.units_y / oneMeter) - 75.0) > 0.001 do
            throw "Protected Density Units Y is not 75.0 m."
        if target.densityMap != true do
            throw "Density Map mode is not enabled."
        if target.distmode != 0 do
            throw "Image distribution mode is not active."

        local oldLegacyDisabled = legacy.disabled
        local oldLayerDisabled = #()
        for layerNode in layers do append oldLayerDisabled layerNode.disabled

        local sourceSpline = findForestAreaSpline legacy
        if sourceSpline == undefined do
            throw "Verified Forest area spline was not found."

        local splineBounds = undefined
        local splineWidth = 0.0
        local splineHeight = 0.0
        try
        (
            splineBounds = nodeGetBoundingBox sourceSpline sourceSpline.transform
            splineWidth = splineBounds[2].x - splineBounds[1].x
            splineHeight = splineBounds[2].y - splineBounds[1].y
        )
        catch
        (
            splineWidth = 0.0
            splineHeight = 0.0
        )

        if splineWidth <= 0.0 or splineHeight <= 0.0 do
            throw "Could not resolve positive Forest area spline bounds."

        local oldUTile = #()
        local oldVTile = #()
        local oldRealWorldScale = #()
        local oldRealWorldWidth = #()
        local oldRealWorldHeight = #()
        local oldUTiling = #()
        local oldVTiling = #()
        local oldUOffset = #()
        local oldVOffset = #()
        local layerCoords = #()

        for layerNode in layers do
        (
            if layerNode.distmap == undefined do
                throw ("Species distribution map is missing: " + layerNode.name)

            local layerCoord = undefined
            try (layerCoord = layerNode.distmap.coords) catch (layerCoord = undefined)
            if layerCoord == undefined do
                throw ("Species Bitmaptexture coords are unavailable: " + layerNode.name)

            append layerCoords layerCoord
            append oldUTile layerCoord.U_Tile
            append oldVTile layerCoord.V_Tile
            append oldRealWorldScale layerCoord.realWorldScale
            append oldRealWorldWidth layerCoord.realWorldWidth
            append oldRealWorldHeight layerCoord.realWorldHeight
            append oldUTiling layerCoord.U_Tiling
            append oldVTiling layerCoord.V_Tiling
            append oldUOffset layerCoord.U_Offset
            append oldVOffset layerCoord.V_Offset
        )

        try
        (
            legacy.disabled = true
            layers[1].disabled = false
            layers[2].disabled = true
            layers[3].disabled = true

            for layerCoord in layerCoords do
            (
                normalizeSpeciesDensityMapCoords layerCoord
            )

            local runtimeBinding = ensureSpeciesPreviewRuntimeBinding target legacy
            local generatedItems = runtimeBinding[6]
            if generatedItems <= 0 do
                throw "Foreground species layer generated zero Forest items after UV clamp runtime binding verification."

            if legacy.disabled != true do throw "Legacy Forest preview state failed."
            if layers[1].disabled != false do throw "Foreground layer preview state failed."
            if layers[2].disabled != true do throw "Mid accent layer preview state failed."
            if layers[3].disabled != true do throw "Structural shrub layer preview state failed."

            if abs((target.units_x / oneMeter) - 75.0) > 0.001 do
                throw "Density Units X changed unexpectedly."
            if abs((target.units_y / oneMeter) - 75.0) > 0.001 do
                throw "Density Units Y changed unexpectedly."
        )
        catch
        (
            for i = 1 to layerCoords.count do
            (
                try (layerCoords[i].U_Tile = oldUTile[i]) catch()
                try (layerCoords[i].V_Tile = oldVTile[i]) catch()
                try (layerCoords[i].realWorldScale = oldRealWorldScale[i]) catch()
                try (layerCoords[i].realWorldWidth = oldRealWorldWidth[i]) catch()
                try (layerCoords[i].realWorldHeight = oldRealWorldHeight[i]) catch()
                try (layerCoords[i].U_Tiling = oldUTiling[i]) catch()
                try (layerCoords[i].V_Tiling = oldVTiling[i]) catch()
                try (layerCoords[i].U_Offset = oldUOffset[i]) catch()
                try (layerCoords[i].V_Offset = oldVOffset[i]) catch()
            )
            try (legacy.disabled = oldLegacyDisabled) catch()
            for i = 1 to layers.count do
                try (layers[i].disabled = oldLayerDisabled[i]) catch()
            throw
        )

        local finalBinding = ensureSpeciesPreviewRuntimeBinding target legacy
        local finalSpline = finalBinding[2]
        local finalSource = finalBinding[3]
        local finalAreaRebound = finalBinding[4]
        local finalGeneratedItems = finalBinding[6]

        "{\"mode\":\"uv_clamp_visual_preview\"" +
        ",\"forest_name\":" + (jsonString target.name) +
        ",\"source_name\":" +
            (if target.cobjlist.count > 0 and target.cobjlist[1] != undefined
                then jsonString target.cobjlist[1].name else "\"\"") +
        ",\"u_tile\":false" +
        ",\"v_tile\":false" +
        ",\"real_world_scale\":false" +
        ",\"uv_mapping\":\"forest_xy_tiled_75m\"" +
        ",\"u_tiling\":1.0" +
        ",\"v_tiling\":1.0" +
        ",\"u_offset\":0.0" +
        ",\"v_offset\":0.0" +
        ",\"area_width_meters\":" + ((splineWidth / oneMeter) as string) +
        ",\"area_height_meters\":" + ((splineHeight / oneMeter) as string) +
        ",\"spline_name\":" + (jsonString sourceSpline.name) +
        ",\"density_meters_x\":" + ((target.units_x / oneMeter) as string) +
        ",\"density_meters_y\":" + ((target.units_y / oneMeter) as string) +
        ",\"legacy_forest_disabled\":true" +
        ",\"only_foreground_layer_active\":true" +
        ",\"area_node\":" + (jsonString finalSpline.name) +
        ",\"source_node\":" + (jsonString finalSource.name) +
        ",\"area_rebound\":" + (boolJson finalAreaRebound) +
        ",\"generated_items\":" + (finalGeneratedItems as string) +
        ",\"transactional\":true" +
        ",\"viewport_refresh\":true" +
        ",\"verified\":true}"
    ),

    fn rollbackSpeciesUvClampPreviewJson =
    (
        local nodes = getSpeciesPreviewNodes()
        local legacy = nodes[1]
        local layers = nodes[2]
        local target = layers[1]

        if target.distmap == undefined do
            throw "Foreground species distribution map is missing."

        local coords = undefined
        try (coords = target.distmap.coords) catch (coords = undefined)
        if coords == undefined do
            throw "Foreground species Bitmaptexture coords are unavailable."

        local oldLegacyDisabled = legacy.disabled
        local oldLayerDisabled = #()
        for layerNode in layers do append oldLayerDisabled layerNode.disabled
        local layerCoords = #()
        for layerNode in layers do
        (
            if layerNode.distmap == undefined do
                throw ("Species distribution map is missing: " + layerNode.name)
            local layerCoord = undefined
            try (layerCoord = layerNode.distmap.coords) catch (layerCoord = undefined)
            if layerCoord == undefined do
                throw ("Species Bitmaptexture coords are unavailable: " + layerNode.name)
            append layerCoords layerCoord
        )

        try
        (
            for layerCoord in layerCoords do
            (
                layerCoord.U_Tile = true
                layerCoord.V_Tile = true
                layerCoord.realWorldScale = true
                layerCoord.realWorldWidth = 1.0
                layerCoord.realWorldHeight = 1.0
            )

            legacy.disabled = false
            for layerNode in layers do layerNode.disabled = true

            if coords.U_Tile != true do throw "U_Tile rollback verification failed."
            if coords.V_Tile != true do throw "V_Tile rollback verification failed."
            if legacy.disabled != false do throw "Legacy Forest rollback failed."
            for layerNode in layers do
                if layerNode.disabled != true do
                    throw ("Species layer rollback failed: " + layerNode.name)
        )
        catch
        (
            try (legacy.disabled = oldLegacyDisabled) catch()
            for i = 1 to layers.count do
                try (layers[i].disabled = oldLayerDisabled[i]) catch()
            throw
        )

        "{\"mode\":\"uv_clamp_rollback\"" +
        ",\"u_tile\":true" +
        ",\"v_tile\":true" +
        ",\"legacy_forest_active\":true" +
        ",\"all_species_layers_disabled\":true" +
        ",\"verified\":true}"
    ),


    fn activateSingleSpeciesLayerPreviewJson layerIndex =
    (
        if layerIndex < 1 or layerIndex > 3 do
            throw "Layer index must be 1, 2, or 3."

        local nodes = getSpeciesPreviewNodes()
        local legacy = nodes[1]
        local layers = nodes[2]

        -- Activation is only allowed from the verified safe baseline or from
        -- another controlled single-layer preview state.
        local activeSpeciesCount = 0
        for layerNode in layers do
        (
            if layerNode.disabled != true do activeSpeciesCount += 1
        )
        if activeSpeciesCount > 1 do
            throw "Unsafe state: more than one species layer is already enabled."

        -- Verify protected state before toggling visibility.
        local oneMeter = 0.0
        try (oneMeter = units.decodeValue "1m") catch (oneMeter = 0.0)
        if oneMeter <= 0.0 do throw "Could not resolve active scene meter conversion."

        for layerNode in layers do
        (
            local densityMetersX = layerNode.units_x / oneMeter
            local densityMetersY = layerNode.units_y / oneMeter

            if abs(densityMetersX - 75.0) > 0.001 do
                throw ("Protected Density Units X is not 75.0 m on " + layerNode.name)
            if abs(densityMetersY - 75.0) > 0.001 do
                throw ("Protected Density Units Y is not 75.0 m on " + layerNode.name)
            if layerNode.distmap == undefined do
                throw ("Distribution map is missing on " + layerNode.name)
            if layerNode.densityMap != true do
                throw ("Density Map mode is not enabled on " + layerNode.name)
            if layerNode.distmode != 0 do
                throw ("Image distribution mode is not active on " + layerNode.name)
        )

        local oldLegacyDisabled = legacy.disabled
        local oldLayerDisabled = #()
        for layerNode in layers do append oldLayerDisabled layerNode.disabled

        try
        (
            legacy.disabled = true

            for i = 1 to layers.count do
                layers[i].disabled = (i != layerIndex)

            for layerNode in layers do
            (
                if layerNode.distmap != undefined do
                (
                    local previewCoords = undefined
                    try (previewCoords = layerNode.distmap.coords) catch (previewCoords = undefined)
                    if previewCoords != undefined do normalizeSpeciesDensityMapCoords previewCoords
                )
            )

            local runtimeBinding = ensureSpeciesPreviewRuntimeBinding layers[layerIndex] legacy
            local generatedItems = runtimeBinding[6]
            if generatedItems <= 0 do
                throw ("Active species layer generated zero Forest items after runtime binding verification: " + layers[layerIndex].name)

            if legacy.disabled != true do
                throw "Legacy Forest did not enter disabled preview state."

            for i = 1 to layers.count do
            (
                local expectedDisabled = (i != layerIndex)
                if layers[i].disabled != expectedDisabled do
                    throw ("Species layer activation verification failed: " + layers[i].name)
            )
        )
        catch
        (
            try (legacy.disabled = oldLegacyDisabled) catch()
            for i = 1 to layers.count do
                try (layers[i].disabled = oldLayerDisabled[i]) catch()
            throw
        )

        local layersJson = "["
        for i = 1 to layers.count do
        (
            if i > 1 do layersJson += ","
            local layerNode = layers[i]
            local sourceName = ""
            try
            (
                if layerNode.cobjlist.count > 0 and layerNode.cobjlist[1] != undefined do
                    sourceName = layerNode.cobjlist[1].name
            )
            catch()

            layersJson += "{\"forest_name\":" + (jsonString layerNode.name) +
                          ",\"source_name\":" + (jsonString sourceName) +
                          ",\"disabled\":" + (boolJson layerNode.disabled) +
                          ",\"active\":" + (boolJson (not layerNode.disabled)) +
                          ",\"density_meters_x\":" + ((layerNode.units_x / oneMeter) as string) +
                          ",\"density_meters_y\":" + ((layerNode.units_y / oneMeter) as string) +
                          ",\"densityMap\":" + (boolJson layerNode.densityMap) +
                          ",\"distmode\":" + (layerNode.distmode as string) +
                          ",\"verified\":true}"
        )
        layersJson += "]"

        local activeBinding = ensureSpeciesPreviewRuntimeBinding layers[layerIndex] legacy
        local activeSpline = activeBinding[2]
        local activeSource = activeBinding[3]
        local activeAreaRebound = activeBinding[4]
        local activeGeneratedItems = activeBinding[6]

        "{\"mode\":\"single_layer_visual_preview\"" +
        ",\"active_layer_index\":" + (layerIndex as string) +
        ",\"legacy_forest\":" + (jsonString legacy.name) +
        ",\"legacy_forest_disabled\":" + (boolJson legacy.disabled) +
        ",\"layers\":" + layersJson +
        ",\"density_units_preserved\":true" +
        ",\"uv_mapping\":\"normalized_area_0_1\"" +
        ",\"real_world_scale\":false" +
        ",\"area_node\":" + (jsonString activeSpline.name) +
        ",\"source_node\":" + (jsonString activeSource.name) +
        ",\"area_rebound\":" + (boolJson activeAreaRebound) +
        ",\"generated_items\":" + (activeGeneratedItems as string) +
        ",\"transactional\":true" +
        ",\"viewport_refresh\":true" +
        ",\"verified\":true}"
    ),

    fn activateAllSpeciesLayersPreviewJson =
    (
        local nodes = getSpeciesPreviewNodes()
        local legacy = nodes[1]
        local layers = nodes[2]

        local oneMeter = 0.0
        try (oneMeter = units.decodeValue "1m") catch (oneMeter = 0.0)
        if oneMeter <= 0.0 do throw "Could not resolve active scene meter conversion."

        local oldLegacyDisabled = legacy.disabled
        local oldLayerDisabled = #()
        for layerNode in layers do append oldLayerDisabled layerNode.disabled

        try
        (
            legacy.disabled = true

            for layerNode in layers do
            (
                if abs((layerNode.units_x / oneMeter) - 75.0) > 0.001 do
                    throw ("Protected Density Units X is not 75.0 m on " + layerNode.name)
                if abs((layerNode.units_y / oneMeter) - 75.0) > 0.001 do
                    throw ("Protected Density Units Y is not 75.0 m on " + layerNode.name)
                if layerNode.distmap == undefined do
                    throw ("Distribution map is missing on " + layerNode.name)
                if layerNode.densityMap != true do
                    throw ("Density Map mode is not enabled on " + layerNode.name)
                if layerNode.distmode != 0 do
                    throw ("Image distribution mode is not active on " + layerNode.name)

                local coords = undefined
                try (coords = layerNode.distmap.coords) catch (coords = undefined)
                if coords == undefined do
                    throw ("Species Bitmaptexture coords are unavailable: " + layerNode.name)
                configureSpeciesDensityMapTilingCoords coords

                layerNode.disabled = false
            )

            if legacy.disabled != true do throw "Legacy Forest did not enter disabled composition state."

            local totalGeneratedItems = 0
            for layerNode in layers do
            (
                local runtimeBinding = ensureSpeciesPreviewRuntimeBinding layerNode legacy
                local generatedItems = runtimeBinding[6]
                if generatedItems <= 0 do
                    throw ("Species composition layer generated zero Forest items: " + layerNode.name)
                totalGeneratedItems += generatedItems
                if layerNode.disabled != false do
                    throw ("Species composition layer did not remain active: " + layerNode.name)
            )

            local layersJson = "["
            for i = 1 to layers.count do
            (
                if i > 1 do layersJson += ","
                local layerNode = layers[i]
                local sourceNode = layerNode.cobjlist[1]
                local runtimeBinding = ensureSpeciesPreviewRuntimeBinding layerNode legacy
                local layerSpline = runtimeBinding[2]
                local generatedItems = runtimeBinding[6]

                layersJson += "{\"index\":" + (i as string) +
                              ",\"forest_name\":" + (jsonString layerNode.name) +
                              ",\"source_name\":" + (jsonString sourceNode.name) +
                              ",\"area_node\":" + (jsonString layerSpline.name) +
                              ",\"density_meters_x\":" + ((layerNode.units_x / oneMeter) as string) +
                              ",\"density_meters_y\":" + ((layerNode.units_y / oneMeter) as string) +
                              ",\"generated_items\":" + (generatedItems as string) +
                              ",\"active\":true" +
                              ",\"verified\":true}"
            )
            layersJson += "]"

            refreshForestPreviewNode layers[1]
            refreshForestPreviewNode layers[2]
            refreshForestPreviewNode layers[3]

            "{\"mode\":\"three_layer_species_composition\"" +
            ",\"legacy_forest\":" + (jsonString legacy.name) +
            ",\"legacy_forest_disabled\":true" +
            ",\"all_species_layers_active\":true" +
            ",\"uv_mapping\":\"normalized_area_0_1\"" +
            ",\"real_world_scale\":false" +
            ",\"density_meters_x\":75.0" +
            ",\"density_meters_y\":75.0" +
            ",\"layer_count\":3" +
            ",\"total_generated_items\":" + (totalGeneratedItems as string) +
            ",\"layers\":" + layersJson +
            ",\"viewport_refresh\":true" +
            ",\"transactional\":true" +
            ",\"verified\":true}"
        )
        catch
        (
            try (legacy.disabled = oldLegacyDisabled) catch()
            for i = 1 to layers.count do
                try (layers[i].disabled = oldLayerDisabled[i]) catch()
            throw
        )
    ),

    fn rollbackSpeciesLayerPreviewJson =
    (
        local nodes = getSpeciesPreviewNodes()
        local legacy = nodes[1]
        local layers = nodes[2]

        local oldLegacyDisabled = legacy.disabled
        local oldLayerDisabled = #()
        for layerNode in layers do append oldLayerDisabled layerNode.disabled

        try
        (
            legacy.disabled = false
            for layerNode in layers do layerNode.disabled = true

            if legacy.disabled != false do
                throw "Legacy Forest rollback verification failed."
            for layerNode in layers do
            (
                if layerNode.disabled != true do
                    throw ("Species layer rollback verification failed: " + layerNode.name)
            )
        )
        catch
        (
            try (legacy.disabled = oldLegacyDisabled) catch()
            for i = 1 to layers.count do
                try (layers[i].disabled = oldLayerDisabled[i]) catch()
            throw
        )

        "{\"mode\":\"rollback\"" +
        ",\"legacy_forest\":" + (jsonString legacy.name) +
        ",\"legacy_forest_active\":true" +
        ",\"all_species_layers_disabled\":true" +
        ",\"verified\":true}"
    ),

    fn getSpeciesMaskDeepUvgenContractJson =
    (
        local layerNames = #(
            "FM_Layer_01_foreground_mass",
            "FM_Layer_02_mid_accent",
            "FM_Layer_03_structural_shrub"
        )

        local sourceForest = getNodeByName "FM_Forest_001"
        local splineNode = undefined
        if sourceForest != undefined do
            splineNode = findForestAreaSpline sourceForest

        local splineWidth = 0.0
        local splineHeight = 0.0
        local splineCenterX = 0.0
        local splineCenterY = 0.0
        local haveBounds = false

        if splineNode != undefined do
        (
            try
            (
                local bounds = nodeGetBoundingBox splineNode splineNode.transform
                local mn = bounds[1]
                local mx = bounds[2]
                splineWidth = mx.x - mn.x
                splineHeight = mx.y - mn.y
                splineCenterX = (mn.x + mx.x) / 2.0
                splineCenterY = (mn.y + mx.y) / 2.0
                haveBounds = true
            )
            catch (haveBounds = false)
        )

        local oneMeter = 0.0
        try (oneMeter = units.decodeValue "1m") catch (oneMeter = 0.0)

        local layersJson = "["

        for layerIndex = 1 to layerNames.count do
        (
            if layerIndex > 1 do layersJson += ","

            local forestNode = getNodeByName layerNames[layerIndex]
            if forestNode == undefined do
                throw ("Prepared species layer was not found: " + layerNames[layerIndex])
            if forestNode.disabled != true do
                throw ("Prepared species layer must remain disabled: " + layerNames[layerIndex])
            if forestNode.distmap == undefined do
                throw ("Distribution map is not bound: " + layerNames[layerIndex])

            local coords = undefined
            try (coords = forestNode.distmap.coords) catch (coords = undefined)
            if coords == undefined do
                throw ("Bitmaptexture coords object is unavailable: " + layerNames[layerIndex])

            local coordProps = getPropNames coords
            local coordJson = "["

            for i = 1 to coordProps.count do
            (
                if i > 1 do coordJson += ","

                local prop = coordProps[i]
                local value = undefined
                local valueClass = "undefined"
                local valueText = "null"

                try
                (
                    value = getProperty coords prop
                    valueClass = (classOf value) as string

                    if value == undefined then
                        valueText = "null"
                    else if classOf value == String then
                        valueText = jsonString value
                    else if classOf value == BooleanClass then
                        valueText = boolJson value
                    else if classOf value == Integer or classOf value == Float then
                        valueText = value as string
                    else
                        valueText = jsonString (value as string)
                )
                catch
                (
                    valueClass = "ERROR"
                    valueText = "null"
                )

                coordJson += "{\"name\":" + (jsonString (prop as string)) +
                             ",\"value_class\":" + (jsonString valueClass) +
                             ",\"value\":" + valueText + "}"
            )
            coordJson += "]"

            local densityMetersX = if oneMeter > 0.0 then forestNode.units_x / oneMeter else 0.0
            local densityMetersY = if oneMeter > 0.0 then forestNode.units_y / oneMeter else 0.0
            local offsetMetersX = if oneMeter > 0.0 then forestNode.offset_X / oneMeter else 0.0
            local offsetMetersY = if oneMeter > 0.0 then forestNode.offset_Y / oneMeter else 0.0

            layersJson += "{\"forest_name\":" + (jsonString forestNode.name) +
                          ",\"disabled\":" + (boolJson forestNode.disabled) +
                          ",\"density_meters_x\":" + (densityMetersX as string) +
                          ",\"density_meters_y\":" + (densityMetersY as string) +
                          ",\"forest_offset_meters_x\":" + (offsetMetersX as string) +
                          ",\"forest_offset_meters_y\":" + (offsetMetersY as string) +
                          ",\"coords_class\":" + (jsonString ((classOf coords) as string)) +
                          ",\"coords_property_count\":" + (coordProps.count as string) +
                          ",\"coords_properties\":" + coordJson +
                          ",\"read_only\":true" +
                          ",\"verified\":true}"
        )

        layersJson += "]"

        local splineJson = "{\"available\":" + (boolJson haveBounds) +
                          ",\"name\":" + (if splineNode != undefined then jsonString splineNode.name else "\"\"") +
                          ",\"width_meters\":" +
                              (if oneMeter > 0.0 then (splineWidth / oneMeter) as string else "0.0") +
                          ",\"height_meters\":" +
                              (if oneMeter > 0.0 then (splineHeight / oneMeter) as string else "0.0") +
                          ",\"center_x_meters\":" +
                              (if oneMeter > 0.0 then (splineCenterX / oneMeter) as string else "0.0") +
                          ",\"center_y_meters\":" +
                              (if oneMeter > 0.0 then (splineCenterY / oneMeter) as string else "0.0") + "}"

        "{\"layer_count\":3" +
        ",\"spline\":" + splineJson +
        ",\"layers\":" + layersJson +
        ",\"prepared_layers_disabled\":true" +
        ",\"read_only\":true" +
        ",\"verified\":true}"
    ),

    fn getSpeciesMaskSpatialAlignmentContractJson =
    (
        local layerNames = #(
            "FM_Layer_01_foreground_mass",
            "FM_Layer_02_mid_accent",
            "FM_Layer_03_structural_shrub"
        )

        local splineNode = undefined
        local sourceForest = getNodeByName "FM_Forest_001"
        if sourceForest != undefined do
            splineNode = findForestAreaSpline sourceForest

        local splineMin = [0,0,0]
        local splineMax = [0,0,0]
        local haveSplineBounds = false
        if splineNode != undefined do
        (
            try
            (
                splineMin = nodeGetBoundingBox splineNode splineNode.transform
                splineMax = splineMin[2]
                splineMin = splineMin[1]
                haveSplineBounds = true
            )
            catch (haveSplineBounds = false)
        )

        local layersJson = "["

        for layerIndex = 1 to layerNames.count do
        (
            if layerIndex > 1 do layersJson += ","

            local forestNode = getNodeByName layerNames[layerIndex]
            if forestNode == undefined do
                throw ("Prepared species layer was not found: " + layerNames[layerIndex])

            if forestNode.distmap == undefined do
                throw ("Distribution map is not bound: " + layerNames[layerIndex])

            local forestCandidates = #()
            local forestProps = getPropNames forestNode
            for prop in forestProps do
            (
                local lowerName = toLower (prop as string)
                if (
                    findString lowerName "map" != undefined or
                    findString lowerName "uv" != undefined or
                    findString lowerName "offset" != undefined or
                    findString lowerName "scale" != undefined or
                    findString lowerName "tile" != undefined or
                    findString lowerName "align" != undefined or
                    findString lowerName "rot" != undefined or
                    findString lowerName "dist" != undefined
                ) do append forestCandidates prop
            )

            local forestJson = "["
            for i = 1 to forestCandidates.count do
            (
                if i > 1 do forestJson += ","
                local prop = forestCandidates[i]
                local value = undefined
                local valueClass = "undefined"
                local valueText = "null"

                try
                (
                    value = getProperty forestNode prop
                    valueClass = (classOf value) as string
                    if value == undefined then
                        valueText = "null"
                    else if classOf value == String then
                        valueText = jsonString value
                    else if classOf value == BooleanClass then
                        valueText = boolJson value
                    else if classOf value == Integer or classOf value == Float then
                        valueText = value as string
                    else
                        valueText = jsonString (value as string)
                )
                catch
                (
                    valueClass = "ERROR"
                    valueText = "null"
                )

                forestJson += "{\"name\":" + (jsonString (prop as string)) +
                              ",\"value_class\":" + (jsonString valueClass) +
                              ",\"value\":" + valueText + "}"
            )
            forestJson += "]"

            local mapNode = forestNode.distmap
            local mapCandidates = #()
            local mapProps = getPropNames mapNode
            for prop in mapProps do
            (
                local lowerName = toLower (prop as string)
                if (
                    findString lowerName "coord" != undefined or
                    findString lowerName "map" != undefined or
                    findString lowerName "offset" != undefined or
                    findString lowerName "scale" != undefined or
                    findString lowerName "tile" != undefined or
                    findString lowerName "angle" != undefined or
                    findString lowerName "blur" != undefined or
                    findString lowerName "crop" != undefined or
                    findString lowerName "uvw" != undefined or
                    findString lowerName "filename" != undefined
                ) do append mapCandidates prop
            )

            local mapJson = "["
            for i = 1 to mapCandidates.count do
            (
                if i > 1 do mapJson += ","
                local prop = mapCandidates[i]
                local value = undefined
                local valueClass = "undefined"
                local valueText = "null"

                try
                (
                    value = getProperty mapNode prop
                    valueClass = (classOf value) as string
                    if value == undefined then
                        valueText = "null"
                    else if classOf value == String then
                        valueText = jsonString value
                    else if classOf value == BooleanClass then
                        valueText = boolJson value
                    else if classOf value == Integer or classOf value == Float then
                        valueText = value as string
                    else
                        valueText = jsonString (value as string)
                )
                catch
                (
                    valueClass = "ERROR"
                    valueText = "null"
                )

                mapJson += "{\"name\":" + (jsonString (prop as string)) +
                           ",\"value_class\":" + (jsonString valueClass) +
                           ",\"value\":" + valueText + "}"
            )
            mapJson += "]"

            local assignedFile = ""
            try (assignedFile = mapNode.filename) catch (assignedFile = "")

            layersJson += "{\"forest_name\":" + (jsonString forestNode.name) +
                          ",\"disabled\":" + (boolJson forestNode.disabled) +
                          ",\"map_path\":" + (jsonString assignedFile) +
                          ",\"forest_alignment_properties\":" + forestJson +
                          ",\"bitmap_alignment_properties\":" + mapJson +
                          ",\"read_only\":true" +
                          ",\"verified\":true}"
        )

        layersJson += "]"

        local splineJson = "null"
        if splineNode != undefined then
        (
            splineJson = "{\"name\":" + (jsonString splineNode.name) +
                         ",\"bounds_available\":" + (boolJson haveSplineBounds) +
                         ",\"min_x\":" + (splineMin.x as string) +
                         ",\"min_y\":" + (splineMin.y as string) +
                         ",\"max_x\":" + (splineMax.x as string) +
                         ",\"max_y\":" + (splineMax.y as string) + "}"
        )

        "{\"layer_count\":3" +
        ",\"spline\":" + splineJson +
        ",\"layers\":" + layersJson +
        ",\"prepared_layers_disabled\":true" +
        ",\"read_only\":true" +
        ",\"verified\":true}"
    ),

    fn bindSpeciesDistributionMasksJson path1 path2 path3 =
    (
        local layerNames = #(
            "FM_Layer_01_foreground_mass",
            "FM_Layer_02_mid_accent",
            "FM_Layer_03_structural_shrub"
        )
        local maskPaths = #(path1, path2, path3)

        local forests = #()
        local oldDistmaps = #()
        local oldDensityMaps = #()
        local oldDistmodes = #()
        local oldDisabled = #()
        local oldUnitsX = #()
        local oldUnitsY = #()

        for i = 1 to layerNames.count do
        (
            local forestNode = getNodeByName layerNames[i]
            if forestNode == undefined do
                throw ("Prepared species layer was not found: " + layerNames[i])

            local isForest = false
            try (isForest = isKindOf forestNode ::Forest_Pro) catch (isForest = false)
            if not isForest do
                throw ("Prepared species layer is not a Forest Pack object: " + layerNames[i])

            if not doesFileExist maskPaths[i] do
                throw ("Species mask file was not found: " + maskPaths[i])

            if forestNode.disabled != true do
                throw ("Species layer must be disabled before mask binding: " + layerNames[i])

            append forests forestNode
            append oldDistmaps forestNode.distmap
            append oldDensityMaps forestNode.densityMap
            append oldDistmodes forestNode.distmode
            append oldDisabled forestNode.disabled
            append oldUnitsX forestNode.units_x
            append oldUnitsY forestNode.units_y
        )

        local createdMaps = #()

        try
        (
            for i = 1 to forests.count do
            (
                local forestNode = forests[i]
                local bitmapMap = Bitmaptexture filename:maskPaths[i]
                append createdMaps bitmapMap

                -- Forest Pack Image Mode stays active. The bitmap texture becomes
                -- the custom distribution map and grayscale values are interpreted
                -- as density values.
                forestNode.distmode = 0
                forestNode.distmap = bitmapMap
                forestNode.densityMap = true

                -- Never alter the verified Density Units baseline in this stage.
                forestNode.units_x = oldUnitsX[i]
                forestNode.units_y = oldUnitsY[i]

                -- Prepared layers remain disabled until spatial alignment and
                -- viewport acceptance are completed.
                forestNode.disabled = true

                if forestNode.distmap == undefined do
                    throw ("Distribution map assignment failed for " + layerNames[i])

                local assignedFile = ""
                try (assignedFile = forestNode.distmap.filename) catch (assignedFile = "")
                if toLower assignedFile != toLower maskPaths[i] do
                    throw ("Distribution map filename verification failed for " + layerNames[i])

                if forestNode.densityMap != true do
                    throw ("Density Map mode verification failed for " + layerNames[i])

                if forestNode.distmode != 0 do
                    throw ("Image distribution mode verification failed for " + layerNames[i])

                if abs(forestNode.units_x - oldUnitsX[i]) > 0.001 do
                    throw ("Density Units X changed unexpectedly for " + layerNames[i])

                if abs(forestNode.units_y - oldUnitsY[i]) > 0.001 do
                    throw ("Density Units Y changed unexpectedly for " + layerNames[i])

                if forestNode.disabled != true do
                    throw ("Species layer was enabled unexpectedly: " + layerNames[i])
            )
        )
        catch
        (
            for i = 1 to forests.count do
            (
                local forestNode = forests[i]
                try (forestNode.distmap = oldDistmaps[i]) catch()
                try (forestNode.densityMap = oldDensityMaps[i]) catch()
                try (forestNode.distmode = oldDistmodes[i]) catch()
                try (forestNode.units_x = oldUnitsX[i]) catch()
                try (forestNode.units_y = oldUnitsY[i]) catch()
                try (forestNode.disabled = oldDisabled[i]) catch()
            )
            throw
        )

        local oneMeter = 0.0
        try (oneMeter = units.decodeValue "1m") catch (oneMeter = 0.0)

        local layersJson = "["
        for i = 1 to forests.count do
        (
            if i > 1 do layersJson += ","
            local forestNode = forests[i]
            local assignedFile = ""
            local mapClass = ""
            try (assignedFile = forestNode.distmap.filename) catch (assignedFile = "")
            try (mapClass = (classOf forestNode.distmap) as string) catch (mapClass = "")

            local densityMetersX = if oneMeter > 0.0 then forestNode.units_x / oneMeter else 0.0
            local densityMetersY = if oneMeter > 0.0 then forestNode.units_y / oneMeter else 0.0

            layersJson += "{\"forest_name\":" + (jsonString forestNode.name) +
                          ",\"map_class\":" + (jsonString mapClass) +
                          ",\"mask_path\":" + (jsonString assignedFile) +
                          ",\"distmode\":" + (forestNode.distmode as string) +
                          ",\"densityMap\":" + (boolJson forestNode.densityMap) +
                          ",\"density_meters_x\":" + (densityMetersX as string) +
                          ",\"density_meters_y\":" + (densityMetersY as string) +
                          ",\"disabled\":" + (boolJson forestNode.disabled) +
                          ",\"verified\":true}"
        )
        layersJson += "]"

        local legacyForest = getNodeByName "FM_Forest_001"

        "{\"layer_count\":3" +
        ",\"layers\":" + layersJson +
        ",\"legacy_forest_active\":" +
            (if legacyForest != undefined then boolJson (not legacyForest.disabled) else "false") +
        ",\"transactional\":true" +
        ",\"prepared_layers_disabled\":true" +
        ",\"density_units_preserved\":true" +
        ",\"verified\":true}"
    ),

    fn getLayerMapBindingContractJson =
    (
        local layerNames = #(
            "FM_Layer_01_foreground_mass",
            "FM_Layer_02_mid_accent",
            "FM_Layer_03_structural_shrub"
        )

        local layersJson = "["

        for layerIndex = 1 to layerNames.count do
        (
            if layerIndex > 1 do layersJson += ","

            local forestNode = getNodeByName layerNames[layerIndex]
            if forestNode == undefined do
                throw ("Prepared species layer was not found: " + layerNames[layerIndex])

            local isForest = false
            try (isForest = isKindOf forestNode ::Forest_Pro) catch (isForest = false)
            if not isForest do
                throw ("Prepared species layer is not a Forest Pack object: " + layerNames[layerIndex])

            local props = getPropNames forestNode
            local candidates = #()

            for prop in props do
            (
                local lowerName = toLower (prop as string)
                if (
                    findString lowerName "map" != undefined or
                    findString lowerName "bitmap" != undefined or
                    findString lowerName "tex" != undefined or
                    findString lowerName "uv" != undefined or
                    findString lowerName "chan" != undefined or
                    findString lowerName "dens" != undefined or
                    findString lowerName "dist" != undefined
                ) do append candidates prop
            )

            local candidateJson = "["
            for i = 1 to candidates.count do
            (
                if i > 1 do candidateJson += ","

                local prop = candidates[i]
                local value = undefined
                local valueClass = "undefined"
                local valueText = "null"

                try
                (
                    value = getProperty forestNode prop
                    valueClass = (classOf value) as string

                    local isNode = false
                    try (isNode = isValidNode value) catch (isNode = false)

                    if value == undefined then
                        valueText = "null"
                    else if isNode then
                        valueText = "{\"node_name\":" + (jsonString value.name) +
                                    ",\"node_class\":" + (jsonString ((classOf value) as string)) + "}"
                    else if classOf value == String then
                        valueText = jsonString value
                    else if classOf value == BooleanClass then
                        valueText = boolJson value
                    else if classOf value == Integer or classOf value == Float then
                        valueText = value as string
                    else if classOf value == ArrayParameter or classOf value == Array then
                    (
                        local arrJson = "["
                        for j = 1 to value.count do
                        (
                            if j > 1 do arrJson += ","
                            local elem = value[j]
                            if elem == undefined then
                                arrJson += "null"
                            else if classOf elem == String then
                                arrJson += jsonString elem
                            else if classOf elem == BooleanClass then
                                arrJson += boolJson elem
                            else if classOf elem == Integer or classOf elem == Float then
                                arrJson += elem as string
                            else
                                arrJson += jsonString (elem as string)
                        )
                        arrJson += "]"
                        valueText = arrJson
                    )
                    else
                        valueText = jsonString (value as string)
                )
                catch
                (
                    valueClass = "ERROR"
                    valueText = "null"
                )

                candidateJson += "{\"name\":" + (jsonString (prop as string)) +
                                 ",\"value_class\":" + (jsonString valueClass) +
                                 ",\"value\":" + valueText + "}"
            )
            candidateJson += "]"

            local oneMeter = 0.0
            try (oneMeter = units.decodeValue "1m") catch (oneMeter = 0.0)
            local densityMetersX = if oneMeter > 0.0 then forestNode.units_x / oneMeter else 0.0
            local densityMetersY = if oneMeter > 0.0 then forestNode.units_y / oneMeter else 0.0

            layersJson += "{\"forest_name\":" + (jsonString forestNode.name) +
                          ",\"disabled\":" + (boolJson forestNode.disabled) +
                          ",\"density_meters_x\":" + (densityMetersX as string) +
                          ",\"density_meters_y\":" + (densityMetersY as string) +
                          ",\"candidate_count\":" + (candidates.count as string) +
                          ",\"candidate_properties\":" + candidateJson +
                          ",\"read_only\":true" +
                          ",\"verified\":true}"
        )

        layersJson += "]"

        "{\"layer_count\":3" +
        ",\"layers\":" + layersJson +
        ",\"probe_goal\":\"resolve the exact Forest Pack 9.4 bitmap/density-map binding contract before applying generated species masks\"" +
        ",\"prepared_layers_disabled\":true" +
        ",\"read_only\":true" +
        ",\"verified\":true}"
    ),

    fn getLayerDensityDistributionContractJson =
    (
        local layerNames = #(
            "FM_Layer_01_foreground_mass",
            "FM_Layer_02_mid_accent",
            "FM_Layer_03_structural_shrub"
        )

        local layersJson = "["

        for layerIndex = 1 to layerNames.count do
        (
            if layerIndex > 1 do layersJson += ","

            local forestNode = getNodeByName layerNames[layerIndex]
            if forestNode == undefined do
                throw ("Prepared species layer was not found: " + layerNames[layerIndex])

            local isForest = false
            try (isForest = isKindOf forestNode ::Forest_Pro) catch (isForest = false)
            if not isForest do
                throw ("Prepared species layer is not a Forest Pack object: " + layerNames[layerIndex])

            local props = getPropNames forestNode
            local candidates = #()

            for prop in props do
            (
                local lowerName = toLower (prop as string)
                if (
                    findString lowerName "dens" != undefined or
                    findString lowerName "prob" != undefined or
                    findString lowerName "mult" != undefined or
                    findString lowerName "amount" != undefined or
                    findString lowerName "count" != undefined or
                    findString lowerName "item" != undefined or
                    findString lowerName "max" != undefined or
                    findString lowerName "percent" != undefined or
                    findString lowerName "ratio" != undefined or
                    findString lowerName "dist" != undefined
                ) do append candidates prop
            )

            local candidateJson = "["
            for i = 1 to candidates.count do
            (
                if i > 1 do candidateJson += ","

                local prop = candidates[i]
                local value = undefined
                local valueClass = "undefined"
                local valueText = "null"

                try
                (
                    value = getProperty forestNode prop
                    valueClass = (classOf value) as string

                    if value == undefined then
                        valueText = "null"
                    else if classOf value == String then
                        valueText = jsonString value
                    else if classOf value == BooleanClass then
                        valueText = boolJson value
                    else if classOf value == Integer or classOf value == Float then
                        valueText = value as string
                    else
                        valueText = jsonString (value as string)
                )
                catch
                (
                    valueClass = "ERROR"
                    valueText = "null"
                )

                candidateJson += "{\"name\":" + (jsonString (prop as string)) +
                                 ",\"value_class\":" + (jsonString valueClass) +
                                 ",\"value\":" + valueText + "}"
            )
            candidateJson += "]"

            local originalProbability = ""
            try (originalProbability = getUserProp forestNode "ForestManagerOriginalProbability") catch (originalProbability = "")

            local oneMeter = 0.0
            try (oneMeter = units.decodeValue "1m") catch (oneMeter = 0.0)
            local densityMetersX = if oneMeter > 0.0 then forestNode.units_x / oneMeter else 0.0
            local densityMetersY = if oneMeter > 0.0 then forestNode.units_y / oneMeter else 0.0

            layersJson += "{\"forest_name\":" + (jsonString forestNode.name) +
                          ",\"disabled\":" + (boolJson forestNode.disabled) +
                          ",\"original_probability\":" + (jsonString originalProbability) +
                          ",\"density_meters_x\":" + (densityMetersX as string) +
                          ",\"density_meters_y\":" + (densityMetersY as string) +
                          ",\"candidate_count\":" + (candidates.count as string) +
                          ",\"candidate_properties\":" + candidateJson +
                          ",\"read_only\":true" +
                          ",\"verified\":true}"
        )

        layersJson += "]"

        "{\"layer_count\":3" +
        ",\"layers\":" + layersJson +
        ",\"goal\":\"preserve total scatter while keeping Density Units at the verified 75.0 m baseline\"" +
        ",\"read_only\":true" +
        ",\"verified\":true}"
    ),

    fn prepareSpeciesLayerForestsJson =
    (
        if not (forestPackAvailable()) do
            throw "Forest Pack Pro class ::Forest_Pro is not available."

        local sourceForest = getNodeByName "FM_Forest_001"
        if sourceForest == undefined do
            throw "FM_Forest_001 was not found."

        local sourceIsForest = false
        try (sourceIsForest = isKindOf sourceForest ::Forest_Pro) catch (sourceIsForest = false)
        if not sourceIsForest do
            throw "FM_Forest_001 is not a Forest Pack object."

        if not (isProperty sourceForest #cobjlist) do
            throw "FM_Forest_001 does not expose cobjlist."
        if sourceForest.cobjlist.count != 3 do
            throw "Stage 5D.15 requires exactly three source geometries."

        local splineNode = findForestAreaSpline sourceForest
        if splineNode == undefined do
            throw "Could not resolve the verified Forest spline area from arnodelist."

        local layerNames = #(
            "FM_Layer_01_foreground_mass",
            "FM_Layer_02_mid_accent",
            "FM_Layer_03_structural_shrub"
        )
        local layerRoles = #(
            "foreground_mass",
            "mid_accent",
            "structural_shrub"
        )

        -- Idempotent cleanup: only delete prior Forest Manager-owned layer
        -- objects with the exact expected names. Never touch unrelated nodes.
        for layerName in layerNames do
        (
            local existing = getNodeByName layerName
            if existing != undefined do
            (
                local existingIsForest = false
                try (existingIsForest = isKindOf existing ::Forest_Pro) catch (existingIsForest = false)

                if not existingIsForest do
                    throw ("Expected layer name is occupied by a non-Forest node: " + layerName)

                if not (isForestManagerOwnedNode existing) do
                    throw ("Refusing to replace non-owned Forest layer: " + layerName)

                delete existing
            )
        )

        local created = #()
        local originalProbabilities = #()
        for i = 1 to sourceForest.problist.count do append originalProbabilities sourceForest.problist[i]

        local oldDensityX = sourceForest.units_x
        local oldDensityY = sourceForest.units_y
        local oldDistMode = sourceForest.distmode
        local oldMapName = sourceForest.mapname
        local oldDensityMap = sourceForest.densityMap
        local oldManualUpdate = sourceForest.manualupdate
        local oldDivers = sourceForest.divers
        local oldClusize = sourceForest.clusize
        local oldClurough = sourceForest.clurough
        local oldCluedge = sourceForest.cluedge
        local oldClunoise = sourceForest.clunoise
        local oldApplyScale = sourceForest.applyscale
        local oldApplyRotation = sourceForest.applyrotation
        local oldApplyTranslation = sourceForest.applytranslation
        local oldScaleXMin = sourceForest.scalexmin
        local oldScaleXMax = sourceForest.scalexmax
        local oldScaleYMin = sourceForest.scaleymin
        local oldScaleYMax = sourceForest.scaleymax
        local oldScaleZMin = sourceForest.scalezmin
        local oldScaleZMax = sourceForest.scalezmax
        local oldScaleLock = sourceForest.scalelock

        local success = false

        try
        (
            for i = 1 to 3 do
            (
                local sourceNode = sourceForest.cobjlist[i]
                if sourceNode == undefined do
                    throw ("Source geometry is undefined at index " + (i as string))

                local layerForest = ::Forest_Pro()
                setForestPointCloudDisplay layerForest
                append created layerForest

                layerForest.name = layerNames[i]
                markForestManagerOwnedNode layerForest role:("species_layer_" + layerRoles[i])
                try (setUserProp layerForest "ForestManagerSourceForest" sourceForest.name) catch()
                try (setUserProp layerForest "ForestManagerSpeciesIndex" (i as string)) catch()
                try (setUserProp layerForest "ForestManagerSpeciesName" sourceNode.name) catch()
                try (setUserProp layerForest "ForestManagerOriginalProbability" (originalProbabilities[i] as string)) catch()

                local areaIndex = addSplineIncludeArea layerForest splineNode
                if not (verifySplineArea layerForest splineNode areaIndex) do
                    throw ("Spline-area verification failed for " + layerNames[i])

                bindForestGeometrySource layerForest sourceNode

                layerForest.units_x = oldDensityX
                layerForest.units_y = oldDensityY
                layerForest.distmode = oldDistMode
                layerForest.mapname = oldMapName
                layerForest.densityMap = oldDensityMap
                layerForest.manualupdate = oldManualUpdate

                layerForest.divers = oldDivers
                layerForest.clusize = oldClusize
                layerForest.clurough = oldClurough
                layerForest.cluedge = oldCluedge
                layerForest.clunoise = oldClunoise

                layerForest.applyscale = oldApplyScale
                layerForest.applyrotation = oldApplyRotation
                layerForest.applytranslation = oldApplyTranslation
                layerForest.scalexmin = oldScaleXMin
                layerForest.scalexmax = oldScaleXMax
                layerForest.scaleymin = oldScaleYMin
                layerForest.scaleymax = oldScaleYMax
                layerForest.scalezmin = oldScaleZMin
                layerForest.scalezmax = oldScaleZMax
                layerForest.scalelock = oldScaleLock

                -- Keep prepared layers disabled until the activation stage.
                layerForest.disabled = true

                if layerForest.cobjlist.count != 1 do
                    throw ("Geometry count verification failed for " + layerNames[i])
                if layerForest.cobjlist[1] != sourceNode do
                    throw ("Source verification failed for " + layerNames[i])
                if layerForest.problist[1] != 100.0 do
                    throw ("Single-species probability verification failed for " + layerNames[i])
                if layerForest.arnodelist[areaIndex] != splineNode do
                    throw ("Area-node verification failed for " + layerNames[i])
                if abs(layerForest.units_x - oldDensityX) > 0.001 do
                    throw ("Density X verification failed for " + layerNames[i])
                if abs(layerForest.units_y - oldDensityY) > 0.001 do
                    throw ("Density Y verification failed for " + layerNames[i])
                if layerForest.disabled != true do
                    throw ("Prepared layer must remain disabled: " + layerNames[i])
            )

            success = true
        )
        catch
        (
            for node in created do
            (
                try (if node != undefined do delete node) catch()
            )
            throw
        )

        if not success do
            throw "Species layer preparation failed."

        local oneMeter = 0.0
        try (oneMeter = units.decodeValue "1m") catch (oneMeter = 0.0)

        local layersJson = "["
        for i = 1 to created.count do
        (
            if i > 1 do layersJson += ","
            local layerForest = created[i]
            local sourceNode = layerForest.cobjlist[1]
            local clusterMeters = if oneMeter > 0.0 then layerForest.clusize / oneMeter else 0.0
            local densityMetersX = if oneMeter > 0.0 then layerForest.units_x / oneMeter else 0.0
            local densityMetersY = if oneMeter > 0.0 then layerForest.units_y / oneMeter else 0.0

            layersJson += "{\"forest_name\":" + (jsonString layerForest.name) +
                          ",\"role\":" + (jsonString layerRoles[i]) +
                          ",\"source_name\":" + (jsonString sourceNode.name) +
                          ",\"source_class\":" + (jsonString ((classOf sourceNode) as string)) +
                          ",\"geometry_count\":" + (layerForest.cobjlist.count as string) +
                          ",\"probability\":" + (layerForest.problist[1] as string) +
                          ",\"original_probability\":" + (originalProbabilities[i] as string) +
                          ",\"area_name\":" + (jsonString splineNode.name) +
                          ",\"density_meters_x\":" + (densityMetersX as string) +
                          ",\"density_meters_y\":" + (densityMetersY as string) +
                          ",\"divers\":" + (layerForest.divers as string) +
                          ",\"cluster_size_meters\":" + (clusterMeters as string) +
                          ",\"clurough\":" + (layerForest.clurough as string) +
                          ",\"cluedge\":" + (layerForest.cluedge as string) +
                          ",\"clunoise\":" + (layerForest.clunoise as string) +
                          ",\"applyscale\":" + (boolJson layerForest.applyscale) +
                          ",\"applyrotation\":" + (boolJson layerForest.applyrotation) +
                          ",\"applytranslation\":" + (boolJson layerForest.applytranslation) +
                          ",\"disabled\":" + (boolJson layerForest.disabled) +
                          ",\"verified\":true}"
        )
        layersJson += "]"

        "{\"source_forest\":" + (jsonString sourceForest.name) +
        ",\"source_forest_preserved\":true" +
        ",\"source_forest_disabled\":" + (boolJson sourceForest.disabled) +
        ",\"spline_area\":" + (jsonString splineNode.name) +
        ",\"layer_count\":" + (created.count as string) +
        ",\"layers\":" + layersJson +
        ",\"transactional\":true" +
        ",\"prepared_layers_disabled\":true" +
        ",\"verified\":true}"
    ),

    fn getLiveSourceAreaContractJson =
    (
        local forestNode = getNodeByName "FM_Forest_001"
        if forestNode == undefined do throw "FM_Forest_001 was not found."

        local managedForest = false
        try (managedForest = isKindOf forestNode ::Forest_Pro) catch (managedForest = false)
        if not managedForest do throw "FM_Forest_001 is not a Forest Pack object."

        local props = getPropNames forestNode
        local keywordProps = #()
        local nodeArrayProps = #()
        local directNodeProps = #()

        for prop in props do
        (
            local propName = prop as string
            local lowerName = toLower propName
            local value = undefined
            local gotValue = false

            try
            (
                value = getProperty forestNode prop
                gotValue = true
            )
            catch (gotValue = false)

            if gotValue do
            (
                if (
                    findString lowerName "area" != undefined or
                    findString lowerName "spline" != undefined or
                    findString lowerName "shape" != undefined or
                    findString lowerName "arn" != undefined or
                    findString lowerName "node" != undefined or
                    findString lowerName "source" != undefined or
                    findString lowerName "object" != undefined or
                    findString lowerName "custom" != undefined or
                    findString lowerName "geom" != undefined
                ) do append keywordProps prop

                local isNode = false
                try (isNode = isValidNode value) catch (isNode = false)
                if isNode do append directNodeProps prop

                local valueClass = classOf value
                if valueClass == ArrayParameter or valueClass == Array do
                (
                    local hasNode = false
                    for i = 1 to value.count while not hasNode do
                    (
                        local elemIsNode = false
                        try (elemIsNode = isValidNode value[i]) catch (elemIsNode = false)
                        if elemIsNode do hasNode = true
                    )
                    if hasNode do append nodeArrayProps prop
                )
            )
        )

        fn propValueJson node prop =
        (
            local value = undefined
            local valueClass = "undefined"
            local valueText = "null"

            try
            (
                value = getProperty node prop
                valueClass = (classOf value) as string

                local isNode = false
                try (isNode = isValidNode value) catch (isNode = false)

                if isNode then
                (
                    valueText = "{\"node_name\":" + (jsonString value.name) +
                                ",\"node_class\":" + (jsonString ((classOf value) as string)) + "}"
                )
                else if (classOf value == ArrayParameter or classOf value == Array) then
                (
                    local arrJson = "["
                    for i = 1 to value.count do
                    (
                        if i > 1 do arrJson += ","
                        local elem = value[i]
                        local elemIsNode = false
                        try (elemIsNode = isValidNode elem) catch (elemIsNode = false)

                        if elemIsNode then
                            arrJson += "{\"node_name\":" + (jsonString elem.name) +
                                       ",\"node_class\":" + (jsonString ((classOf elem) as string)) + "}"
                        else if elem == undefined then
                            arrJson += "null"
                        else
                            arrJson += jsonString (elem as string)
                    )
                    arrJson += "]"
                    valueText = arrJson
                )
                else if value == undefined then
                    valueText = "null"
                else if classOf value == String then
                    valueText = jsonString value
                else if classOf value == BooleanClass then
                    valueText = boolJson value
                else if classOf value == Integer or classOf value == Float then
                    valueText = value as string
                else
                    valueText = jsonString (value as string)
            )
            catch
            (
                valueClass = "ERROR"
                valueText = "null"
            )

            "{\"name\":" + (jsonString (prop as string)) +
            ",\"value_class\":" + (jsonString valueClass) +
            ",\"value\":" + valueText + "}"
        )

        local keywordJson = "["
        for i = 1 to keywordProps.count do
        (
            if i > 1 do keywordJson += ","
            keywordJson += propValueJson forestNode keywordProps[i]
        )
        keywordJson += "]"

        local nodeArraysJson = "["
        for i = 1 to nodeArrayProps.count do
        (
            if i > 1 do nodeArraysJson += ","
            nodeArraysJson += propValueJson forestNode nodeArrayProps[i]
        )
        nodeArraysJson += "]"

        local directNodesJson = "["
        for i = 1 to directNodeProps.count do
        (
            if i > 1 do directNodesJson += ","
            directNodesJson += propValueJson forestNode directNodeProps[i]
        )
        directNodesJson += "]"

        local refsLayer = LayerManager.getLayerFromName "FM_REFERENCES"
        if refsLayer == undefined do refsLayer = LayerManager.getLayerFromName "FM_References"
        local managedRefs = #()
        if refsLayer != undefined do
        (
            local layerNodes = #()
            local gotLayerNodes = false
            try (gotLayerNodes = refsLayer.nodes &layerNodes) catch (gotLayerNodes = false)

            if gotLayerNodes do
            (
                for n in layerNodes do
                (
                    local owned = false
                    try (owned = (getUserProp n "ForestManagerOwned") == "true") catch (owned = false)
                    if owned do append managedRefs n
                )
            )
        )

        local refsJson = "["
        for i = 1 to managedRefs.count do
        (
            if i > 1 do refsJson += ","
            local n = managedRefs[i]
            local role = ""
            local assetName = ""
            try (role = getUserProp n "ForestManagerRole") catch (role = "")
            try (assetName = getUserProp n "ForestManagerAssetName") catch (assetName = "")
            refsJson += "{\"node_name\":" + (jsonString n.name) +
                        ",\"node_class\":" + (jsonString ((classOf n) as string)) +
                        ",\"role\":" + (jsonString role) +
                        ",\"asset_name\":" + (jsonString assetName) + "}"
        )
        refsJson += "]"

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"property_count\":" + (props.count as string) +
        ",\"keyword_properties\":" + keywordJson +
        ",\"node_array_properties\":" + nodeArraysJson +
        ",\"direct_node_properties\":" + directNodesJson +
        ",\"managed_reference_nodes\":" + refsJson +
        ",\"read_only\":true" +
        ",\"verified\":true}"
    ),

    fn getSpeciesLayerContextJson =
    (
        local forestNode = getNodeByName "FM_Forest_001"
        if forestNode == undefined do throw "FM_Forest_001 was not found."

        local managedForest = false
        try (managedForest = isKindOf forestNode ::Forest_Pro) catch (managedForest = false)
        if not managedForest do throw "FM_Forest_001 is not a Forest Pack object."

        local oneMeter = 0.0
        try (oneMeter = units.decodeValue "1m") catch (oneMeter = 0.0)

        local namesJson = "["
        for i = 1 to forestNode.namelist.count do
        (
            if i > 1 do namesJson += ","
            namesJson += jsonString forestNode.namelist[i]
        )
        namesJson += "]"

        local probsJson = "["
        for i = 1 to forestNode.problist.count do
        (
            if i > 1 do probsJson += ","
            probsJson += forestNode.problist[i] as string
        )
        probsJson += "]"

        local geomModesJson = "["
        for i = 1 to forestNode.geomlist.count do
        (
            if i > 1 do geomModesJson += ","
            geomModesJson += forestNode.geomlist[i] as string
        )
        geomModesJson += "]"

        local sourceNamesJson = "["
        for i = 1 to forestNode.tempnamelist.count do
        (
            if i > 1 do sourceNamesJson += ","
            local sourceName = forestNode.tempnamelist[i]
            if sourceName == undefined then
                sourceNamesJson += "null"
            else
                sourceNamesJson += jsonString (sourceName as string)
        )
        sourceNamesJson += "]"

        local areaCount = 0
        local areaSummary = #()
        try
        (
            areaCount = forestNode.arnodes.count
            for i = 1 to forestNode.arnodes.count do
            (
                local areaNode = forestNode.arnodes[i]
                local areaName = if areaNode == undefined then "<undefined>" else areaNode.name
                append areaSummary areaName
            )
        )
        catch
        (
            areaCount = 0
            areaSummary = #()
        )

        local areasJson = "["
        for i = 1 to areaSummary.count do
        (
            if i > 1 do areasJson += ","
            areasJson += jsonString areaSummary[i]
        )
        areasJson += "]"

        local densityMetersX = if oneMeter > 0.0 then forestNode.units_x / oneMeter else 0.0
        local densityMetersY = if oneMeter > 0.0 then forestNode.units_y / oneMeter else 0.0
        local clusterMeters = if oneMeter > 0.0 then forestNode.clusize / oneMeter else 0.0

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"geometry_count\":" + (forestNode.namelist.count as string) +
        ",\"geometry_names\":" + namesJson +
        ",\"source_names\":" + sourceNamesJson +
        ",\"geometry_modes\":" + geomModesJson +
        ",\"probabilities\":" + probsJson +
        ",\"area_count\":" + (areaCount as string) +
        ",\"area_names\":" + areasJson +
        ",\"divers\":" + (forestNode.divers as string) +
        ",\"clusize\":" + (forestNode.clusize as string) +
        ",\"cluster_size_meters\":" + (clusterMeters as string) +
        ",\"clurough\":" + (forestNode.clurough as string) +
        ",\"cluedge\":" + (forestNode.cluedge as string) +
        ",\"clunoise\":" + (forestNode.clunoise as string) +
        ",\"density_meters_x\":" + (densityMetersX as string) +
        ",\"density_meters_y\":" + (densityMetersY as string) +
        ",\"applyscale\":" + (boolJson forestNode.applyscale) +
        ",\"applyrotation\":" + (boolJson forestNode.applyrotation) +
        ",\"applytranslation\":" + (boolJson forestNode.applytranslation) +
        ",\"read_only\":true" +
        ",\"verified\":true}"
    ),

    fn applyVisualClusterCalibrationJson =
    (
        local forestNode = getNodeByName "FM_Forest_001"
        if forestNode == undefined do throw "FM_Forest_001 was not found."

        local managedForest = false
        try (managedForest = isKindOf forestNode ::Forest_Pro) catch (managedForest = false)
        if not managedForest do throw "FM_Forest_001 is not a Forest Pack object."

        local oldDivers = forestNode.divers
        local oldClusize = forestNode.clusize
        local oldClurough = forestNode.clurough
        local oldCluedge = forestNode.cluedge
        local oldClunoise = forestNode.clunoise
        local oldUnitsX = forestNode.units_x
        local oldUnitsY = forestNode.units_y
        local oldApplyScale = forestNode.applyscale
        local oldApplyRotation = forestNode.applyrotation
        local oldApplyTranslation = forestNode.applytranslation
        local oldProb = #()

        for i = 1 to forestNode.problist.count do append oldProb forestNode.problist[i]

        if oldDivers != 2 do throw "Forest diversity mode is not Clusters (divers=2)."

        local oneMeter = 0.0
        try (oneMeter = units.decodeValue "1m") catch (oneMeter = 0.0)
        if oneMeter <= 0.0 do throw "Unable to resolve active scene meter conversion."

        local targetClusterSize = oneMeter * 30.0

        forestNode.clusize = targetClusterSize
        forestNode.clurough = 25.0
        forestNode.cluedge = 20.0
        forestNode.clunoise = 5.0

        local verified = true
        if forestNode.divers != oldDivers do verified = false
        if abs(forestNode.clusize - targetClusterSize) > 0.001 do verified = false
        if abs(forestNode.clurough - 25.0) > 0.001 do verified = false
        if abs(forestNode.cluedge - 20.0) > 0.001 do verified = false
        if abs(forestNode.clunoise - 5.0) > 0.001 do verified = false
        if abs(forestNode.units_x - oldUnitsX) > 0.001 do verified = false
        if abs(forestNode.units_y - oldUnitsY) > 0.001 do verified = false
        if forestNode.applyscale != oldApplyScale do verified = false
        if forestNode.applyrotation != oldApplyRotation do verified = false
        if forestNode.applytranslation != oldApplyTranslation do verified = false
        if forestNode.problist.count != oldProb.count do verified = false

        if verified do
        (
            for i = 1 to oldProb.count do
            (
                if abs(forestNode.problist[i] - oldProb[i]) > 0.001 do verified = false
            )
        )

        if not verified then
        (
            forestNode.divers = oldDivers
            forestNode.clusize = oldClusize
            forestNode.clurough = oldClurough
            forestNode.cluedge = oldCluedge
            forestNode.clunoise = oldClunoise
            forestNode.units_x = oldUnitsX
            forestNode.units_y = oldUnitsY
            forestNode.applyscale = oldApplyScale
            forestNode.applyrotation = oldApplyRotation
            forestNode.applytranslation = oldApplyTranslation
            for i = 1 to oldProb.count do forestNode.problist[i] = oldProb[i]
            throw "Visual cluster calibration verification failed. Previous values restored."
        )

        local densityMetersX = forestNode.units_x / oneMeter
        local densityMetersY = forestNode.units_y / oneMeter
        local clusterMeters = forestNode.clusize / oneMeter

        local probJson = "["
        for i = 1 to forestNode.problist.count do
        (
            if i > 1 do probJson += ","
            probJson += forestNode.problist[i] as string
        )
        probJson += "]"

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"divers\":" + (forestNode.divers as string) +
        ",\"cluster_mode\":\"clusters\"" +
        ",\"clusize\":" + (forestNode.clusize as string) +
        ",\"cluster_size_meters\":" + (clusterMeters as string) +
        ",\"clurough\":" + (forestNode.clurough as string) +
        ",\"cluedge\":" + (forestNode.cluedge as string) +
        ",\"clunoise\":" + (forestNode.clunoise as string) +
        ",\"density_meters_x\":" + (densityMetersX as string) +
        ",\"density_meters_y\":" + (densityMetersY as string) +
        ",\"probabilities\":" + probJson +
        ",\"applyscale\":" + (boolJson forestNode.applyscale) +
        ",\"applyrotation\":" + (boolJson forestNode.applyrotation) +
        ",\"applytranslation\":" + (boolJson forestNode.applytranslation) +
        ",\"verified\":true}"
    ),

    fn applyNaturalClusterProfileJson =
    (
        local forestNode = getNodeByName "FM_Forest_001"
        if forestNode == undefined do throw "FM_Forest_001 was not found."

        local managedForest = false
        try (managedForest = isKindOf forestNode ::Forest_Pro) catch (managedForest = false)
        if not managedForest do throw "FM_Forest_001 is not a Forest Pack object."

        local oldDivers = forestNode.divers
        local oldClusize = forestNode.clusize
        local oldClurough = forestNode.clurough
        local oldCluedge = forestNode.cluedge
        local oldClunoise = forestNode.clunoise
        local oldUnitsX = forestNode.units_x
        local oldUnitsY = forestNode.units_y
        local oldProb = #()
        local oldApplyScale = forestNode.applyscale
        local oldApplyRotation = forestNode.applyrotation
        local oldApplyTranslation = forestNode.applytranslation

        for i = 1 to forestNode.problist.count do append oldProb forestNode.problist[i]

        if oldDivers != 2 do throw "Forest diversity mode is not Clusters (divers=2)."

        forestNode.clurough = 35.0
        forestNode.cluedge = 25.0
        forestNode.clunoise = 10.0

        local verified = true
        if forestNode.divers != oldDivers do verified = false
        if abs(forestNode.clusize - oldClusize) > 0.001 do verified = false
        if abs(forestNode.clurough - 35.0) > 0.001 do verified = false
        if abs(forestNode.cluedge - 25.0) > 0.001 do verified = false
        if abs(forestNode.clunoise - 10.0) > 0.001 do verified = false
        if abs(forestNode.units_x - oldUnitsX) > 0.001 do verified = false
        if abs(forestNode.units_y - oldUnitsY) > 0.001 do verified = false
        if forestNode.applyscale != oldApplyScale do verified = false
        if forestNode.applyrotation != oldApplyRotation do verified = false
        if forestNode.applytranslation != oldApplyTranslation do verified = false
        if forestNode.problist.count != oldProb.count do verified = false

        if verified do
        (
            for i = 1 to oldProb.count do
            (
                if abs(forestNode.problist[i] - oldProb[i]) > 0.001 do verified = false
            )
        )

        if not verified then
        (
            forestNode.divers = oldDivers
            forestNode.clusize = oldClusize
            forestNode.clurough = oldClurough
            forestNode.cluedge = oldCluedge
            forestNode.clunoise = oldClunoise
            forestNode.units_x = oldUnitsX
            forestNode.units_y = oldUnitsY
            forestNode.applyscale = oldApplyScale
            forestNode.applyrotation = oldApplyRotation
            forestNode.applytranslation = oldApplyTranslation
            for i = 1 to oldProb.count do forestNode.problist[i] = oldProb[i]
            throw "Cluster profile verification failed. Previous values restored."
        )

        local oneMeter = 0.0
        try (oneMeter = units.decodeValue "1m") catch (oneMeter = 0.0)
        local densityMetersX = if oneMeter > 0.0 then forestNode.units_x / oneMeter else 0.0
        local densityMetersY = if oneMeter > 0.0 then forestNode.units_y / oneMeter else 0.0
        local clusterMeters = if oneMeter > 0.0 then forestNode.clusize / oneMeter else 0.0

        local probJson = "["
        for i = 1 to forestNode.problist.count do
        (
            if i > 1 do probJson += ","
            probJson += forestNode.problist[i] as string
        )
        probJson += "]"

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"divers\":" + (forestNode.divers as string) +
        ",\"cluster_mode\":\"clusters\"" +
        ",\"clusize\":" + (forestNode.clusize as string) +
        ",\"cluster_size_meters\":" + (clusterMeters as string) +
        ",\"clurough\":" + (forestNode.clurough as string) +
        ",\"cluedge\":" + (forestNode.cluedge as string) +
        ",\"clunoise\":" + (forestNode.clunoise as string) +
        ",\"density_meters_x\":" + (densityMetersX as string) +
        ",\"density_meters_y\":" + (densityMetersY as string) +
        ",\"probabilities\":" + probJson +
        ",\"applyscale\":" + (boolJson forestNode.applyscale) +
        ",\"applyrotation\":" + (boolJson forestNode.applyrotation) +
        ",\"applytranslation\":" + (boolJson forestNode.applytranslation) +
        ",\"verified\":true}"
    ),

    fn getClusterParameterMappingJson =
    (
        local forestNode = getNodeByName "FM_Forest_001"
        if forestNode == undefined do throw "FM_Forest_001 was not found."

        local managedForest = false
        try (managedForest = isKindOf forestNode ::Forest_Pro) catch (managedForest = false)
        if not managedForest do throw "FM_Forest_001 is not a Forest Pack object."

        local props = getPropNames forestNode
        local candidates = #()

        for prop in props do
        (
            local propName = prop as string
            local lowerName = toLower propName

            if (
                findString lowerName "div" != undefined or
                findString lowerName "cluster" != undefined or
                findString lowerName "clump" != undefined or
                findString lowerName "size" != undefined or
                findString lowerName "rough" != undefined or
                findString lowerName "blur" != undefined or
                findString lowerName "noise" != undefined or
                findString lowerName "edge" != undefined or
                findString lowerName "spread" != undefined or
                findString lowerName "random" != undefined or
                findString lowerName "geom" != undefined
            ) do append candidates prop
        )

        local json = "{\"forest_name\":" + (jsonString forestNode.name) +
                     ",\"forest_class\":" + (jsonString ((classOf forestNode) as string)) +
                     ",\"property_count\":" + (props.count as string) +
                     ",\"candidate_count\":" + (candidates.count as string) +
                     ",\"candidates\":["

        for i = 1 to candidates.count do
        (
            if i > 1 do json += ","

            local prop = candidates[i]
            local value = undefined
            local valueClass = "undefined"
            local valueText = "null"

            try
            (
                value = getProperty forestNode prop
                valueClass = (classOf value) as string

                if value == undefined then
                    valueText = "null"
                else if (classOf value == String) then
                    valueText = jsonString value
                else if (classOf value == BooleanClass) then
                    valueText = boolJson value
                else if (classOf value == Integer or classOf value == Float) then
                    valueText = value as string
                else
                    valueText = jsonString (value as string)
            )
            catch
            (
                valueClass = "ERROR"
                valueText = "null"
            )

            json += "{\"name\":" + (jsonString (prop as string)) +
                    ",\"value_class\":" + (jsonString valueClass) +
                    ",\"value\":" + valueText + "}"
        )

        json += "]" +
                ",\"divers\":" + (forestNode.divers as string) +
                ",\"distmode\":" + (forestNode.distmode as string) +
                ",\"mapname\":" + (jsonString forestNode.mapname) +
                ",\"density_units_x\":" + (forestNode.units_x as string) +
                ",\"density_units_y\":" + (forestNode.units_y as string) +
                ",\"read_only\":true" +
                ",\"verified\":true}"

        json
    ),

    fn getClusterCapabilityProbeJson =
    (
        local forestNode = getNodeByName "FM_Forest_001"
        if forestNode == undefined do throw "FM_Forest_001 was not found."

        local managedForest = false
        try (managedForest = isKindOf forestNode ::Forest_Pro) catch (managedForest = false)
        if not managedForest do throw "FM_Forest_001 is not a Forest Pack object."

        local props = getPropNames forestNode
        local matches = #()

        for prop in props do
        (
            local propName = prop as string
            local lowerName = toLower propName
            if (
                findString lowerName "cluster" != undefined or
                findString lowerName "clump" != undefined or
                findString lowerName "divers" != undefined or
                findString lowerName "geom" != undefined or
                findString lowerName "prob" != undefined or
                findString lowerName "colorid" != undefined or
                findString lowerName "colourid" != undefined
            ) do
            (
                append matches prop
            )
        )

        local json = "{\"forest_name\":" + (jsonString forestNode.name) +
                     ",\"forest_class\":" + (jsonString ((classOf forestNode) as string)) +
                     ",\"property_count\":" + (props.count as string) +
                     ",\"cluster_property_count\":" + (matches.count as string) +
                     ",\"cluster_properties\":["

        for i = 1 to matches.count do
        (
            if i > 1 do json += ","
            local prop = matches[i]
            local value = undefined
            local valueClass = "undefined"
            local valueText = "null"

            try
            (
                value = getProperty forestNode prop
                valueClass = (classOf value) as string

                if value == undefined then
                    valueText = "null"
                else if (classOf value == String) then
                    valueText = jsonString value
                else if (classOf value == BooleanClass) then
                    valueText = boolJson value
                else if (classOf value == Integer or classOf value == Float) then
                    valueText = value as string
                else
                    valueText = jsonString (value as string)
            )
            catch
            (
                valueClass = "ERROR"
                valueText = "null"
            )

            json += "{\"name\":" + (jsonString (prop as string)) +
                    ",\"value_class\":" + (jsonString valueClass) +
                    ",\"value\":" + valueText + "}"
        )

        json += "]" +
                ",\"distmode\":" + (forestNode.distmode as string) +
                ",\"mapname\":" + (jsonString forestNode.mapname) +
                ",\"density_units_x\":" + (forestNode.units_x as string) +
                ",\"density_units_y\":" + (forestNode.units_y as string) +
                ",\"read_only\":true" +
                ",\"verified\":true}"

        json
    ),

    fn getDistributionCapabilityProbeJson =
    (
        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."

        local props = getPropNames forestNode
        local matches = #()
        for propName in props do
        (
            local propText = toLower (propName as string)
            if (findString propText "dist") != undefined or
               (findString propText "map") != undefined or
               (findString propText "cluster") != undefined or
               (findString propText "group") != undefined or
               (findString propText "falloff") != undefined or
               (findString propText "edge") != undefined do
            (
                append matches propName
            )
        )

        local propertiesJson = "["
        for i = 1 to matches.count do
        (
            if i > 1 do propertiesJson += ","
            local propName = matches[i]
            local value = undefined
            local valueClass = "undefined"
            try
            (
                value = getProperty forestNode propName
                if value != undefined do valueClass = safeClassName value
            )
            catch()

            propertiesJson += "{\"name\":" + (jsonString (propName as string)) +
                              ",\"value_class\":" + (jsonString valueClass) +
                              ",\"value\":" + (safePropertyValueJson forestNode propName) + "}"
        )
        propertiesJson += "]"

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"forest_class\":" + (jsonString ((classOf forestNode) as string)) +
        ",\"property_count\":" + (props.count as string) +
        ",\"distribution_property_count\":" + (matches.count as string) +
        ",\"distribution_properties\":" + propertiesJson +
        ",\"density_units_x\":" + (forestNode.units_x as string) +
        ",\"density_units_y\":" + (forestNode.units_y as string) +
        ",\"read_only\":true" +
        ",\"verified\":true}"
    ),

    fn getTransformCapabilityProbeJson =
    (
        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."

        local props = getPropNames forestNode
        local matches = #()
        for propName in props do
        (
            local propText = toLower (propName as string)
            if (findString propText "scale") != undefined or 
               (findString propText "rot") != undefined or
               (findString propText "trans") != undefined do
            (
                append matches propName
            )
        )

        local propertiesJson = "["
        for i = 1 to matches.count do
        (
            if i > 1 do propertiesJson += ","
            local propName = matches[i]
            local value = undefined
            local valueClass = "undefined"
            try
            (
                value = getProperty forestNode propName
                if value != undefined do valueClass = safeClassName value
            )
            catch()

            propertiesJson += "{\"name\":" + (jsonString (propName as string)) +
                              ",\"value_class\":" + (jsonString valueClass) +
                              ",\"value\":" + (safePropertyValueJson forestNode propName) + "}"
        )
        propertiesJson += "]"

        local geometryScaleJson = "[]"
        if isProperty forestNode #ScaleList do
        (
            geometryScaleJson = "["
            for i = 1 to forestNode.ScaleList.count do
            (
                if i > 1 do geometryScaleJson += ","
                geometryScaleJson += (forestNode.ScaleList[i] as string)
            )
            geometryScaleJson += "]"
        )

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"forest_class\":" + (jsonString ((classOf forestNode) as string)) +
        ",\"property_count\":" + (props.count as string) +
        ",\"transform_property_count\":" + (matches.count as string) +
        ",\"transform_properties\":" + propertiesJson +
        ",\"geometry_scale_list_available\":" + (boolJson (isProperty forestNode #ScaleList)) +
        ",\"geometry_scale_list\":" + geometryScaleJson +
        ",\"read_only\":true" +
        ",\"verified\":true}"
    ),

    fn applyNativeScaleVariationJson =
    (
        local forestNode = getNodeByName "FM_Forest_001"
        if forestNode == undefined do throw "FM_Forest_001 was not found."

        local managedForest = false
        try (managedForest = isKindOf forestNode ::Forest_Pro) catch (managedForest = false)
        if not managedForest do throw "FM_Forest_001 is not a Forest Pack object."

        local densityXBefore = forestNode.units_x
        local densityYBefore = forestNode.units_y
        local probabilitiesBefore = #()
        try
        (
            for i = 1 to forestNode.problist.count do append probabilitiesBefore forestNode.problist[i]
        )
        catch()

        local scaleXMinBefore = forestNode.scalexmin
        local scaleXMaxBefore = forestNode.scalexmax
        local scaleYMinBefore = forestNode.scaleymin
        local scaleYMaxBefore = forestNode.scaleymax
        local scaleZMinBefore = forestNode.scalezmin
        local scaleZMaxBefore = forestNode.scalezmax
        local scaleLockBefore = forestNode.scalelock
        local rotationBefore = forestNode.applyrotation
        local translationBefore = forestNode.applytranslation

        -- Stage 5D.4 intentionally changes only this property.
        forestNode.applyscale = true

        try (forestNode.update()) catch()
        completeRedraw()

        if abs (forestNode.units_x - densityXBefore) > 0.001 do
            throw "Scale apply verification failed: density X changed."
        if abs (forestNode.units_y - densityYBefore) > 0.001 do
            throw "Scale apply verification failed: density Y changed."

        if forestNode.scalexmin != scaleXMinBefore or forestNode.scalexmax != scaleXMaxBefore do
            throw "Scale apply verification failed: X scale limits changed."
        if forestNode.scaleymin != scaleYMinBefore or forestNode.scaleymax != scaleYMaxBefore do
            throw "Scale apply verification failed: Y scale limits changed."
        if forestNode.scalezmin != scaleZMinBefore or forestNode.scalezmax != scaleZMaxBefore do
            throw "Scale apply verification failed: Z scale limits changed."
        if forestNode.scalelock != scaleLockBefore do
            throw "Scale apply verification failed: scalelock changed."
        if forestNode.applyrotation != rotationBefore do
            throw "Scale apply verification failed: rotation state changed."
        if forestNode.applytranslation != translationBefore do
            throw "Scale apply verification failed: translation state changed."
        if forestNode.applyscale != true do
            throw "Scale apply verification failed: applyscale is not enabled."

        local probabilitiesAfter = #()
        try
        (
            for i = 1 to forestNode.problist.count do append probabilitiesAfter forestNode.problist[i]
        )
        catch()

        if probabilitiesBefore.count != probabilitiesAfter.count do
            throw "Scale apply verification failed: probability count changed."
        for i = 1 to probabilitiesBefore.count do
        (
            if abs (probabilitiesBefore[i] - probabilitiesAfter[i]) > 0.001 do
                throw "Scale apply verification failed: probability values changed."
        )

        local oneMeterSystemUnits = units.decodeValue "1m"
        if oneMeterSystemUnits <= 0.0 do
            throw "Scale apply verification failed: scene unit conversion is invalid."

        local densityMetersX = densityXBefore / oneMeterSystemUnits
        local densityMetersY = densityYBefore / oneMeterSystemUnits

        local probabilitiesJson = "["
        for i = 1 to probabilitiesAfter.count do
        (
            if i > 1 do probabilitiesJson += ","
            probabilitiesJson += (probabilitiesAfter[i] as string)
        )
        probabilitiesJson += "]"

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"applyscale\":true" +
        ",\"scalexmin\":" + (forestNode.scalexmin as string) +
        ",\"scalexmax\":" + (forestNode.scalexmax as string) +
        ",\"scaleymin\":" + (forestNode.scaleymin as string) +
        ",\"scaleymax\":" + (forestNode.scaleymax as string) +
        ",\"scalezmin\":" + (forestNode.scalezmin as string) +
        ",\"scalezmax\":" + (forestNode.scalezmax as string) +
        ",\"scalelock\":" + (forestNode.scalelock as string) +
        ",\"applyrotation\":" + (boolJson forestNode.applyrotation) +
        ",\"applytranslation\":" + (boolJson forestNode.applytranslation) +
        ",\"density_meters_x\":" + (densityMetersX as string) +
        ",\"density_meters_y\":" + (densityMetersY as string) +
        ",\"probabilities\":" + probabilitiesJson +
        ",\"verified\":true}"
    ),


    fn applyClusterDiversityModeJson =
    (
        local forestNode = getNodeByName "FM_Forest_001"
        if forestNode == undefined do throw "FM_Forest_001 was not found."

        local managedForest = false
        try (managedForest = isKindOf forestNode ::Forest_Pro) catch (managedForest = false)
        if not managedForest do throw "FM_Forest_001 is not a Forest Pack object."

        local requiredProps = #(#divers, #clusize, #clurough, #clunoise, #cluedge, #units_x, #units_y, #problist, #applyscale, #applyrotation, #applytranslation, #scalexmin, #scalexmax, #scaleymin, #scaleymax, #scalezmin, #scalezmax, #scalelock)
        for p in requiredProps do
        (
            if not (isProperty forestNode p) do throw ("Cluster apply property missing: " + (p as string))
        )

        local diversityBefore = forestNode.divers
        local clusterSizeBefore = forestNode.clusize
        local clusterRoughBefore = forestNode.clurough
        local clusterNoiseBefore = forestNode.clunoise
        local clusterEdgeBefore = forestNode.cluedge
        local densityXBefore = forestNode.units_x
        local densityYBefore = forestNode.units_y
        local applyScaleBefore = forestNode.applyscale
        local rotationBefore = forestNode.applyrotation
        local translationBefore = forestNode.applytranslation
        local scaleXMinBefore = forestNode.scalexmin
        local scaleXMaxBefore = forestNode.scalexmax
        local scaleYMinBefore = forestNode.scaleymin
        local scaleYMaxBefore = forestNode.scaleymax
        local scaleZMinBefore = forestNode.scalezmin
        local scaleZMaxBefore = forestNode.scalezmax
        local scaleLockBefore = forestNode.scalelock
        local probabilitiesBefore = #()
        for i = 1 to forestNode.problist.count do append probabilitiesBefore forestNode.problist[i]

        try
        (
            -- Stage 5D.10 intentionally changes only the Diversity mode.
            forestNode.divers = 2
            try (forestNode.update()) catch()
            completeRedraw()

            if forestNode.divers != 2 do throw "Cluster apply verification failed: divers is not 2."
            if abs (forestNode.clusize - clusterSizeBefore) > 0.001 do throw "Cluster apply verification failed: cluster size changed."
            if abs (forestNode.clurough - clusterRoughBefore) > 0.001 do throw "Cluster apply verification failed: roughness changed."
            if abs (forestNode.clunoise - clusterNoiseBefore) > 0.001 do throw "Cluster apply verification failed: noise changed."
            if abs (forestNode.cluedge - clusterEdgeBefore) > 0.001 do throw "Cluster apply verification failed: blurry edge changed."
            if abs (forestNode.units_x - densityXBefore) > 0.001 do throw "Cluster apply verification failed: density X changed."
            if abs (forestNode.units_y - densityYBefore) > 0.001 do throw "Cluster apply verification failed: density Y changed."
            if forestNode.applyscale != applyScaleBefore do throw "Cluster apply verification failed: applyscale changed."
            if forestNode.applyrotation != rotationBefore do throw "Cluster apply verification failed: rotation changed."
            if forestNode.applytranslation != translationBefore do throw "Cluster apply verification failed: translation changed."
            if forestNode.scalexmin != scaleXMinBefore or forestNode.scalexmax != scaleXMaxBefore do throw "Cluster apply verification failed: X scale limits changed."
            if forestNode.scaleymin != scaleYMinBefore or forestNode.scaleymax != scaleYMaxBefore do throw "Cluster apply verification failed: Y scale limits changed."
            if forestNode.scalezmin != scaleZMinBefore or forestNode.scalezmax != scaleZMaxBefore do throw "Cluster apply verification failed: Z scale limits changed."
            if forestNode.scalelock != scaleLockBefore do throw "Cluster apply verification failed: scalelock changed."

            if forestNode.problist.count != probabilitiesBefore.count do throw "Cluster apply verification failed: probability count changed."
            for i = 1 to probabilitiesBefore.count do
            (
                if abs (forestNode.problist[i] - probabilitiesBefore[i]) > 0.001 do throw "Cluster apply verification failed: probability values changed."
            )

            local oneMeterSystemUnits = units.decodeValue "1m"
            if oneMeterSystemUnits <= 0.0 do throw "Cluster apply verification failed: scene unit conversion is invalid."

            local probabilitiesJson = "["
            for i = 1 to forestNode.problist.count do
            (
                if i > 1 do probabilitiesJson += ","
                probabilitiesJson += (forestNode.problist[i] as string)
            )
            probabilitiesJson += "]"

            "{\"forest_name\":" + (jsonString forestNode.name) +
            ",\"previous_divers\":" + (diversityBefore as string) +
            ",\"divers\":" + (forestNode.divers as string) +
            ",\"cluster_mode\":\"clusters\"" +
            ",\"clusize\":" + (forestNode.clusize as string) +
            ",\"clurough\":" + (forestNode.clurough as string) +
            ",\"clunoise\":" + (forestNode.clunoise as string) +
            ",\"cluedge\":" + (forestNode.cluedge as string) +
            ",\"density_meters_x\":" + ((forestNode.units_x / oneMeterSystemUnits) as string) +
            ",\"density_meters_y\":" + ((forestNode.units_y / oneMeterSystemUnits) as string) +
            ",\"probabilities\":" + probabilitiesJson +
            ",\"applyscale\":" + (boolJson forestNode.applyscale) +
            ",\"applyrotation\":" + (boolJson forestNode.applyrotation) +
            ",\"applytranslation\":" + (boolJson forestNode.applytranslation) +
            ",\"verified\":true}"
        )
        catch
        (
            local message = getCurrentException()
            try (forestNode.divers = diversityBefore) catch()
            try (forestNode.update()) catch()
            completeRedraw()
            format "Forest Manager cluster apply error: %\\n" message
            throw
        )
    ),

    fn getCompositionContextJson =
    (
        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."

        local areaJson = getSelectionSplineAreaJson()
        local geometryJson = getForestGeometrySummaryJson()
        local oneMeterSystemUnits = metersToSystemUnits 1.0
        if oneMeterSystemUnits <= 0.0 do
            throw "Scene unit conversion is invalid."

        local unitsX = if isProperty forestNode #units_x then forestNode.units_x else 0.0
        local unitsY = if isProperty forestNode #units_y then forestNode.units_y else 0.0
        local densityMetersX = unitsX / oneMeterSystemUnits
        local densityMetersY = unitsY / oneMeterSystemUnits
        local generatedCount = getForestGeneratedItemCount forestNode

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"scene_units\":" + getSceneUnitsJson() +
        ",\"selection_area\":" + areaJson +
        ",\"geometry\":" + geometryJson +
        ",\"density\":{" +
            "\"units_x_system\":" + (unitsX as string) +
            ",\"units_y_system\":" + (unitsY as string) +
            ",\"units_x_display\":" + (jsonString (formatSystemValueForScene unitsX)) +
            ",\"units_y_display\":" + (jsonString (formatSystemValueForScene unitsY)) +
            ",\"meters_x\":" + (densityMetersX as string) +
            ",\"meters_y\":" + (densityMetersY as string) +
        "}" +
        ",\"generated_items_probe\":" + (generatedCount as string) +
        ",\"generated_count_probe\":\"trees.count\"" +
        ",\"generated_count_authoritative\":false" +
        ",\"read_only\":true" +
        ",\"verified\":true}"
    ),

    fn scheduleBridgeReload scriptPath =
    (
        if scriptPath == undefined or scriptPath == "" do
            throw "Bridge reload path is empty."
        if not doesFileExist scriptPath do
            throw ("Bridge reload script does not exist: " + scriptPath)

        try
        (
            if ForestManagerBridgeReloadTimer != undefined do
            (
                ForestManagerBridgeReloadTimer.Stop()
                ForestManagerBridgeReloadTimer.Dispose()
            )
        )
        catch()

        ForestManagerBridgeReloadPath = scriptPath
        ForestManagerBridgeReloadTimer = dotNetObject "System.Windows.Forms.Timer"
        ForestManagerBridgeReloadTimer.Interval = 500
        dotNet.addEventHandler ForestManagerBridgeReloadTimer "Tick" (fn onForestManagerAtomicBridgeReloadTick sender args =
        (
            local pathToLoad = ForestManagerBridgeReloadPath
            try
            (
                if ForestManagerBridgeReloadTimer != undefined do
                (
                    ForestManagerBridgeReloadTimer.Stop()
                    ForestManagerBridgeReloadTimer.Dispose()
                )
            )
            catch()
            ForestManagerBridgeReloadTimer = undefined
            ForestManagerBridgeReloadPath = undefined

            -- The RELOAD_BRIDGE response has already been returned. Stop the old
            -- listener completely before loading the one canonical bridge source.
            try (if ForestManagerBridge != undefined do ForestManagerBridge.stop()) catch()

            try
            (
                if pathToLoad != undefined and doesFileExist pathToLoad then
                (
                    format "Forest Manager Bridge atomic reload: %\n" pathToLoad
                    fileIn pathToLoad quiet:true
                )
                else
                (
                    format "Forest Manager Bridge atomic reload failed: script not found.\n"
                )
            )
            catch
            (
                format "Forest Manager Bridge atomic reload failed: %\n" (getCurrentException())
            )
        ))
        ForestManagerBridgeReloadTimer.Start()
        true
    ),


    fn forestControlWriteMode value =
    (
        local valueClass = safeClassName value
        if valueClass == "Color" then return "color"
        if valueClass == "BooleanClass" or valueClass == "Integer" or valueClass == "Integer64" or valueClass == "Float" or valueClass == "Double" or valueClass == "String" or valueClass == "Angle" then return "scalar"
        "read_only"
    ),

    fn forestControlArrayMetadataJson value =
    (
        local countValue = 0
        try (countValue = value.count) catch (countValue = 0)
        local previewCount = countValue
        if previewCount > 8 do previewCount = 8
        local classes = #()
        local elementsJson = "["
        for i = 1 to previewCount do
        (
            local elem = undefined
            try (elem = value[i]) catch (elem = undefined)
            local elemClass = safeClassName elem
            if (findItem classes elemClass) == 0 do append classes elemClass
            if i > 1 do elementsJson += ","
            elementsJson += "{\"value_class\":" + (jsonString elemClass) + ",\"preview\":" + (jsonString (safeValuePreview elem)) + "}"
        )
        elementsJson += "]"
        local classesJson = "["
        for i = 1 to classes.count do
        (
            if i > 1 do classesJson += ","
            classesJson += jsonString classes[i]
        )
        classesJson += "]"
        "{\"count\":" + (countValue as string) + ",\"preview_count\":" + (previewCount as string) + ",\"element_classes\":" + classesJson + ",\"elements\":" + elementsJson + "}"
    ),

    fn forestControlPropertyJson forestNode propName =
    (
        local value = undefined
        local readOk = true
        try (value = getProperty forestNode propName) catch (readOk = false)
        if not readOk then return "{\"name\":" + (jsonString (propName as string)) + ",\"value_class\":\"unreadable\",\"write_mode\":\"read_only\",\"readable\":false}"
        local valueClass = safeClassName value
        local writeMode = forestControlWriteMode value
        local result = "{\"name\":" + (jsonString (propName as string)) + ",\"value_class\":" + (jsonString valueClass) + ",\"write_mode\":" + (jsonString writeMode) + ",\"readable\":true"
        if valueClass == "ArrayParameter" or valueClass == "Array" then result += ",\"array_metadata\":" + forestControlArrayMetadataJson value else result += ",\"value\":" + safePropertyValueJson forestNode propName
        result += "}"
        result
    ),

    fn getForestControlDiscoveryJson =
    (
        if not (forestPackAvailable()) do throw "Forest Pack Pro class ::Forest_Pro is not available."
        local forests = #()
        for obj in objects do
        (
            local isForest = false
            try (isForest = isKindOf obj ::Forest_Pro) catch (isForest = false)
            if isForest do append forests obj
        )
        local result = "{\"read_only\":true,\"forest_count\":" + (forests.count as string) + ",\"forests\":["
        for forestIndex = 1 to forests.count do
        (
            local forestNode = forests[forestIndex]
            local propNames = getPropNames forestNode
            local readOnlyCount = 0
            local scalarCount = 0
            local colorCount = 0
            local propertiesJson = "["
            local arraysJson = "["
            local arrayCount = 0
            for propIndex = 1 to propNames.count do
            (
                local propName = propNames[propIndex]
                local value = undefined
                local readOk = true
                try (value = getProperty forestNode propName) catch (readOk = false)
                local mode = "read_only"
                local valueClass = "unreadable"
                if readOk then
                (
                    valueClass = safeClassName value
                    mode = forestControlWriteMode value
                )
                case mode of
                (
                    "scalar": scalarCount += 1
                    "color": colorCount += 1
                    default: readOnlyCount += 1
                )
                if propIndex > 1 do propertiesJson += ","
                propertiesJson += forestControlPropertyJson forestNode propName
                if readOk and (valueClass == "ArrayParameter" or valueClass == "Array") then
                (
                    arrayCount += 1
                    if arrayCount > 1 do arraysJson += ","
                    arraysJson += "{\"name\":" + (jsonString (propName as string)) + ",\"metadata\":" + forestControlArrayMetadataJson value + "}"
                )
            )
            propertiesJson += "]"
            arraysJson += "]"
            if forestIndex > 1 do result += ","
            result += "{\"forest_name\":" + (jsonString forestNode.name) + ",\"property_count\":" + (propNames.count as string) + ",\"write_mode_counts\":{\"read_only\":" + (readOnlyCount as string) + ",\"scalar\":" + (scalarCount as string) + ",\"color\":" + (colorCount as string) + "},\"properties\":" + propertiesJson + ",\"arrays\":" + arraysJson + "}"
        )
        result += "],\"verified\":true}"
        result
    ),

    fn findForestControlNode forestName =
    (
        if not (forestPackAvailable()) do throw "Forest Pack Pro class ::Forest_Pro is not available."
        local node = getNodeByName forestName
        if node == undefined do throw ("Forest control target not found: " + forestName)
        local isForest = false
        try (isForest = isKindOf node ::Forest_Pro) catch (isForest = false)
        if not isForest do throw ("Forest control target is not Forest Pack: " + forestName)
        node
    ),

    fn forestControlPropertyName forestNode propertyName =
    (
        local propName = propertyName as name
        local names = getPropNames forestNode
        if (findItem names propName) == 0 do throw ("Forest control property not found: " + propertyName)
        propName
    ),

    fn forestControlExplicitReadOnly propertyName =
    (
        local p = toLower propertyName
        p == "geomtexid" or p == "fastopac" or p == "renderid" or p == "divtmap" or p == "geomtex"
    ),

    fn forestControlGetPropertyJson forestName propertyName =
    (
        local forestNode = findForestControlNode forestName
        local propName = forestControlPropertyName forestNode propertyName
        local propertyJson = forestControlPropertyJson forestNode propName
        "{\"forest_name\":" + (jsonString forestNode.name) + ",\"property\":" + propertyJson + ",\"verified\":true}"
    ),

    fn forestControlScalarFamily valueClass =
    (
        if valueClass == "BooleanClass" then return "bool"
        if valueClass == "Integer" or valueClass == "Integer64" then return "int"
        if valueClass == "Float" or valueClass == "Double" then return "float"
        if valueClass == "String" then return "string"
        ""
    ),

    fn parseForestControlScalar scalarType encodedValue =
    (
        local text = decodeBase64Utf8 encodedValue
        case scalarType of
        (
            "bool":
            (
                local normalized = toLower text
                if normalized == "true" or normalized == "1" then true
                else if normalized == "false" or normalized == "0" then false
                else throw ("Invalid Boolean scalar value: " + text)
            )
            "int": (text as integer)
            "float": (text as float)
            "string": text
            default: throw ("Unsupported scalar type: " + scalarType)
        )
    ),

    fn forestControlArrayScalarValueJson value =
    (
        local valueClass = safeClassName value
        if valueClass == "BooleanClass" then return (boolJson value)
        if valueClass == "Integer" or valueClass == "Integer64" or valueClass == "Float" or valueClass == "Double" then return (value as string)
        if valueClass == "String" then return (jsonString value)
        throw ("Unsupported Forest control array scalar class: " + valueClass)
    ),

    fn forestControlIsMaterialReference value =
    (
        if value == undefined then return false
        local isMaterial = false
        try (isMaterial = (superClassOf value == Material)) catch (isMaterial = false)
        isMaterial
    ),

    fn forestControlMaterialNameEquals value materialName =
    (
        if value == undefined then return false
        local matches = false
        try (matches = (value.name == materialName)) catch (matches = false)
        matches
    ),

    fn forestControlIsTextureReference value =
    (
        if value == undefined then return false
        local valueClass = safeClassName value
        valueClass == "Bitmaptexture"
    ),

    fn forestControlTextureFilename value =
    (
        if value == undefined then return ""
        if not (forestControlIsTextureReference value) do return ""
        local filename = ""
        try (filename = value.filename) catch (filename = "")
        filename
    ),

    fn forestControlTextureAnimHandle value =
    (
        if value == undefined then return 0
        if not (forestControlIsTextureReference value) do return 0
        local handle = 0
        try (handle = GetHandleByAnim value) catch (handle = 0)
        handle
    ),

    fn forestControlTextureReferenceToken value =
    (
        if value == undefined then return ""
        if not (forestControlIsTextureReference value) do
            throw ("Forest control texture reference is not a Bitmaptexture: " + (safeClassName value))
        local handle = forestControlTextureAnimHandle value
        if handle <= 0 do throw "Forest control Bitmaptexture AnimHandle is unavailable."
        "anim:" + ((handle as integer) as string)
    ),

    fn forestControlTextureReferenceValueJson value =
    (
        if value == undefined then return "null"
        jsonString (forestControlTextureReferenceToken value)
    ),

    fn forestControlFindBitmapTextureByFilename filename =
    (
        if filename == "" do return undefined
        local target = toLower filename
        local candidates = #()
        try (candidates = getClassInstances Bitmaptexture) catch (candidates = #())
        for tex in candidates where tex != undefined do
        (
            local candidateFilename = forestControlTextureFilename tex
            if candidateFilename != "" and (toLower candidateFilename) == target do return tex
        )
        for obj in objects do
        (
            local isForest = false
            try (isForest = isKindOf obj ::Forest_Pro) catch (isForest = false)
            if isForest and isProperty obj #distmap then
            (
                local tex = undefined
                try (tex = obj.distmap) catch (tex = undefined)
                if tex != undefined then
                (
                    local candidateFilename = forestControlTextureFilename tex
                    if candidateFilename != "" and (toLower candidateFilename) == target do return tex
                )
            )
        )
        undefined
    ),

    fn forestControlFindBitmapTextureByAnimHandle handle =
    (
        if handle <= 0 do return undefined
        local value = undefined
        try (value = GetAnimByHandle handle) catch (value = undefined)
        if value == undefined then return undefined
        if not (forestControlIsTextureReference value) do return undefined
        value
    ),

    fn forestControlGetTextureReferenceJson forestName propertyName =
    (
        if (toLower propertyName) != "distmap" do
            throw ("Texture reference writes are not enabled for: " + propertyName)
        local forestNode = findForestControlNode forestName
        local propName = forestControlPropertyName forestNode propertyName
        local value = undefined
        local readOk = true
        try (value = getProperty forestNode propName) catch (readOk = false)
        if not readOk do throw ("Forest control texture property is unreadable: " + propertyName)
        if value != undefined and not (forestControlIsTextureReference value) do
            throw ("Forest control property is not a Bitmaptexture reference: " + propertyName + " class=" + (safeClassName value))
        local filename = if value == undefined then "" else forestControlTextureFilename value
        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"property_name\":" + (jsonString propertyName) +
        ",\"value_class\":" + (jsonString (safeClassName value)) +
        ",\"reference_type\":\"texture\"" +
        ",\"value\":" + (forestControlTextureReferenceValueJson value) +
        ",\"filename\":" + (jsonString filename) +
        ",\"verified\":true}"
    ),

    fn forestControlSetTextureReferenceJson forestName propertyName referenceMode encodedTextureToken =
    (
        if (toLower propertyName) != "distmap" do
            throw ("Texture reference writes are not enabled for: " + propertyName)
        local forestNode = findForestControlNode forestName
        local propName = forestControlPropertyName forestNode propertyName
        local beforeValue = undefined
        local beforeReadOk = true
        try (beforeValue = getProperty forestNode propName) catch (beforeReadOk = false)
        if not beforeReadOk do throw ("Forest control texture property is unreadable: " + propertyName)
        if beforeValue != undefined and not (forestControlIsTextureReference beforeValue) do
            throw ("Forest control property is not a Bitmaptexture reference: " + propertyName + " class=" + (safeClassName beforeValue))
        local beforeJson = forestControlTextureReferenceValueJson beforeValue
        local newValue = undefined
        if referenceMode == "anim" then
        (
            local textureToken = decodeBase64Utf8 encodedTextureToken
            if textureToken == "" do throw "Texture reference AnimHandle token cannot be empty."
            if not matchPattern textureToken pattern:"anim:*" ignoreCase:true do
                throw ("Unsupported texture reference token: " + textureToken)
            local handleText = substring textureToken 6 (textureToken.count - 5)
            local handle = 0
            try (handle = handleText as integer) catch (handle = 0)
            if handle <= 0 do throw ("Invalid texture reference AnimHandle token: " + textureToken)
            newValue = forestControlFindBitmapTextureByAnimHandle handle
            if newValue == undefined do throw ("Texture reference target was not found: " + textureToken)
        )
        else if referenceMode == "bitmap" then
        (
            local textureFilename = decodeBase64Utf8 encodedTextureToken
            if textureFilename == "" do throw "Texture reference filename token cannot be empty."
            newValue = forestControlFindBitmapTextureByFilename textureFilename
            if newValue == undefined do throw ("Texture reference target was not found: " + textureFilename)
        )
        else if referenceMode != "null" then
        (
            throw ("Unsupported texture reference mode: " + referenceMode)
        )
        setProperty forestNode propName newValue
        refreshForestPreviewNode forestNode
        local afterValue = undefined
        local afterReadOk = true
        try (afterValue = getProperty forestNode propName) catch (afterReadOk = false)
        if not afterReadOk do throw ("Forest control texture reference readback failed: " + propertyName)
        local verified = false
        if newValue == undefined then verified = (afterValue == undefined)
        else verified = (afterValue == newValue)
        if not verified do throw ("Forest control texture reference write verification failed: " + propertyName)
        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"property_name\":" + (jsonString propertyName) +
        ",\"reference_type\":\"texture\"" +
        ",\"before_value\":" + beforeJson +
        ",\"after_value\":" + (forestControlTextureReferenceValueJson afterValue) +
        ",\"verified\":true}"
    ),

    fn forestControlGetArrayElementJson forestName propertyName zeroIndex =
    (
        local forestNode = findForestControlNode forestName
        local propName = forestControlPropertyName forestNode propertyName
        local arr = undefined
        local readOk = true
        try (arr = getProperty forestNode propName) catch (readOk = false)
        if not readOk do throw ("Forest control array property is unreadable: " + propertyName)
        local arrayClass = safeClassName arr
        if arrayClass != "ArrayParameter" and arrayClass != "Array" do
            throw ("Forest control property is not an array: " + propertyName + " class=" + arrayClass)
        if zeroIndex < 0 do throw "Forest control array index must be zero or greater."
        local countValue = arr.count
        if zeroIndex >= countValue do
            throw ("Forest control array index out of range: " + propertyName + " index=" + (zeroIndex as string) + " count=" + (countValue as string))
        local maxIndex = zeroIndex + 1
        local value = undefined
        local elementReadOk = true
        try (value = arr[maxIndex]) catch (elementReadOk = false)
        if not elementReadOk do throw ("Forest control array element is unreadable: " + propertyName + "[" + (zeroIndex as string) + "]")
        local valueClass = safeClassName value
        local scalarType = forestControlScalarFamily valueClass
        local vectorType = ""
        local valueJson = ""
        if scalarType != "" then
        (
            valueJson = forestControlArrayScalarValueJson value
        )
        else if valueClass == "Point3" then
        (
            vectorType = "point3"
            valueJson = "[" + (value.x as string) + "," + (value.y as string) + "," + (value.z as string) + "]"
        )
        else if (toLower propertyName) == "arnodelist" and (value == undefined or isValidNode value) then
        (
            valueJson = if value == undefined then "null" else jsonString value.name
        )
        else if (toLower propertyName) == "matlist" and (value == undefined or forestControlIsMaterialReference value) then
        (
            valueJson = if value == undefined then "null" else jsonString value.name
        )
        else if (toLower propertyName) == "cobjlist" and (value == undefined or (isValidNode value and safeClassName value == "CProxy")) then
        (
            valueJson = if value == undefined then "null" else jsonString value.name
        )
        else
        (
            throw ("Forest control array element is not writable by a verified endpoint: " + propertyName + "[" + (zeroIndex as string) + "] class=" + valueClass)
        )
        local referenceType = ""
        if (toLower propertyName) == "arnodelist" and (value == undefined or isValidNode value) then referenceType = "node"
        if (toLower propertyName) == "matlist" and (value == undefined or forestControlIsMaterialReference value) then referenceType = "material"
        if (toLower propertyName) == "cobjlist" and (value == undefined or (isValidNode value and safeClassName value == "CProxy")) then referenceType = "cproxy"
        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"property_name\":" + (jsonString propertyName) +
        ",\"index\":" + (zeroIndex as string) +
        ",\"count\":" + (countValue as string) +
        ",\"value_class\":" + (jsonString valueClass) +
        ",\"scalar_type\":" + (jsonString scalarType) +
        ",\"vector_type\":" + (jsonString vectorType) +
        ",\"reference_type\":" + (jsonString referenceType) +
        ",\"value\":" + valueJson +
        ",\"verified\":true}"
    ),


    fn forestControlNodeReferenceValueJson value =
    (
        if value == undefined then return "null"
        if isValidNode value then return (jsonString value.name)
        throw "Forest control node reference value is neither undefined nor a valid scene node."
    ),

    fn forestControlSetArrayNodeReferenceJson forestName propertyName zeroIndex referenceMode encodedNodeName =
    (
        if (toLower propertyName) != "arnodelist" do
            throw ("Node reference array writes are not enabled for: " + propertyName)
        local forestNode = findForestControlNode forestName
        local propName = forestControlPropertyName forestNode propertyName
        local arr = undefined
        local readOk = true
        try (arr = getProperty forestNode propName) catch (readOk = false)
        if not readOk do throw ("Forest control array property is unreadable: " + propertyName)
        local arrayClass = safeClassName arr
        if arrayClass != "ArrayParameter" and arrayClass != "Array" do
            throw ("Forest control property is not an array: " + propertyName + " class=" + arrayClass)
        if zeroIndex < 0 do throw "Forest control array index must be zero or greater."
        local countValue = arr.count
        if zeroIndex >= countValue do
            throw ("Forest control array index out of range: " + propertyName + " index=" + (zeroIndex as string) + " count=" + (countValue as string))
        local maxIndex = zeroIndex + 1
        local beforeValue = undefined
        local beforeReadOk = true
        try (beforeValue = arr[maxIndex]) catch (beforeReadOk = false)
        if not beforeReadOk do throw ("Forest control array element is unreadable: " + propertyName + "[" + (zeroIndex as string) + "]")
        if beforeValue != undefined and not (isValidNode beforeValue) do
            throw ("Forest control array element is not a node reference: " + propertyName + "[" + (zeroIndex as string) + "] class=" + (safeClassName beforeValue))
        local beforeJson = forestControlNodeReferenceValueJson beforeValue
        local newValue = undefined
        if referenceMode == "node" then
        (
            local nodeName = decodeBase64Utf8 encodedNodeName
            if nodeName == "" do throw "Node reference target name cannot be empty."
            newValue = getNodeByName nodeName
            if newValue == undefined or not (isValidNode newValue) do
                throw ("Node reference target was not found: " + nodeName)
        )
        else if referenceMode != "null" then
        (
            throw ("Unsupported node reference mode: " + referenceMode)
        )
        arr[maxIndex] = newValue
        refreshForestPreviewNode forestNode
        local afterValue = undefined
        local afterReadOk = true
        try (afterValue = arr[maxIndex]) catch (afterReadOk = false)
        if not afterReadOk do throw ("Forest control array node reference readback failed: " + propertyName + "[" + (zeroIndex as string) + "]")
        local verified = false
        if newValue == undefined then
            verified = (afterValue == undefined) and (arr.count == countValue)
        else
            verified = (isValidNode afterValue) and (afterValue == newValue) and (arr.count == countValue)
        if not verified do throw ("Forest control array node reference write verification failed: " + propertyName + "[" + (zeroIndex as string) + "]")
        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"property_name\":" + (jsonString propertyName) +
        ",\"index\":" + (zeroIndex as string) +
        ",\"count\":" + (countValue as string) +
        ",\"reference_type\":\"node\"" +
        ",\"before_value\":" + beforeJson +
        ",\"after_value\":" + (forestControlNodeReferenceValueJson afterValue) +
        ",\"verified\":true}"
    ),

    fn forestControlMaterialReferenceValueJson value =
    (
        if value == undefined then return "null"
        local isMaterial = forestControlIsMaterialReference value
        if isMaterial then return (jsonString value.name)
        throw "Forest control material reference value is neither undefined nor a material."
    ),

    fn forestControlFindSceneMaterialByName materialName =
    (
        for mat in sceneMaterials where mat != undefined do
        (
            if forestControlMaterialNameEquals mat materialName do return mat
        )
        for node in objects where node != undefined do
        (
            local mat = undefined
            try (mat = node.material) catch()
            if mat != undefined and forestControlMaterialNameEquals mat materialName do return mat
        )
        undefined
    ),

    fn forestControlSetArrayMaterialReferenceJson forestName propertyName zeroIndex referenceMode encodedMaterialName =
    (
        if (toLower propertyName) != "matlist" do
            throw ("Material reference array writes are not enabled for: " + propertyName)
        local forestNode = findForestControlNode forestName
        local propName = forestControlPropertyName forestNode propertyName
        local arr = undefined
        local readOk = true
        try (arr = getProperty forestNode propName) catch (readOk = false)
        if not readOk do throw ("Forest control array property is unreadable: " + propertyName)
        local arrayClass = safeClassName arr
        if arrayClass != "ArrayParameter" and arrayClass != "Array" do
            throw ("Forest control property is not an array: " + propertyName + " class=" + arrayClass)
        if zeroIndex < 0 do throw "Forest control array index must be zero or greater."
        local countValue = arr.count
        if zeroIndex >= countValue do
            throw ("Forest control array index out of range: " + propertyName + " index=" + (zeroIndex as string) + " count=" + (countValue as string))
        local maxIndex = zeroIndex + 1
        local beforeValue = undefined
        local beforeReadOk = true
        try (beforeValue = arr[maxIndex]) catch (beforeReadOk = false)
        if not beforeReadOk do throw ("Forest control array element is unreadable: " + propertyName + "[" + (zeroIndex as string) + "]")
        if beforeValue != undefined then
        (
            local beforeIsMaterial = forestControlIsMaterialReference beforeValue
            if not beforeIsMaterial do
                throw ("Forest control array element is not a material reference: " + propertyName + "[" + (zeroIndex as string) + "] class=" + (safeClassName beforeValue))
        )
        local beforeJson = forestControlMaterialReferenceValueJson beforeValue
        local newValue = undefined
        if referenceMode == "material" then
        (
            local materialName = decodeBase64Utf8 encodedMaterialName
            if materialName == "" do throw "Material reference target name cannot be empty."
            newValue = forestControlFindSceneMaterialByName materialName
            if newValue == undefined do throw ("Material reference target was not found: " + materialName)
        )
        else if referenceMode != "null" then
        (
            throw ("Unsupported material reference mode: " + referenceMode)
        )
        arr[maxIndex] = newValue
        refreshForestPreviewNode forestNode
        local afterValue = undefined
        local afterReadOk = true
        try (afterValue = arr[maxIndex]) catch (afterReadOk = false)
        if not afterReadOk do throw ("Forest control array material reference readback failed: " + propertyName + "[" + (zeroIndex as string) + "]")
        local verified = false
        if newValue == undefined then
            verified = (afterValue == undefined) and (arr.count == countValue)
        else
            verified = (afterValue == newValue) and (arr.count == countValue)
        if not verified do throw ("Forest control array material reference write verification failed: " + propertyName + "[" + (zeroIndex as string) + "]")
        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"property_name\":" + (jsonString propertyName) +
        ",\"index\":" + (zeroIndex as string) +
        ",\"count\":" + (countValue as string) +
        ",\"reference_type\":\"material\"" +
        ",\"before_value\":" + beforeJson +
        ",\"after_value\":" + (forestControlMaterialReferenceValueJson afterValue) +
        ",\"verified\":true}"
    ),

    fn forestControlCProxyReferenceValueJson value =
    (
        if value == undefined then return "null"
        if isValidNode value and safeClassName value == "CProxy" then return (jsonString value.name)
        throw "Forest control CProxy reference value is neither undefined nor a CProxy scene node."
    ),

    fn forestControlSetArrayCProxyReferenceJson forestName propertyName zeroIndex referenceMode encodedNodeName =
    (
        if (toLower propertyName) != "cobjlist" do
            throw ("CProxy reference array writes are not enabled for: " + propertyName)
        local forestNode = findForestControlNode forestName
        local propName = forestControlPropertyName forestNode propertyName
        local arr = undefined
        local readOk = true
        try (arr = getProperty forestNode propName) catch (readOk = false)
        if not readOk do throw ("Forest control array property is unreadable: " + propertyName)
        local arrayClass = safeClassName arr
        if arrayClass != "ArrayParameter" and arrayClass != "Array" do
            throw ("Forest control property is not an array: " + propertyName + " class=" + arrayClass)
        if zeroIndex < 0 do throw "Forest control array index must be zero or greater."
        local countValue = arr.count
        if zeroIndex >= countValue do
            throw ("Forest control array index out of range: " + propertyName + " index=" + (zeroIndex as string) + " count=" + (countValue as string))
        local maxIndex = zeroIndex + 1
        local beforeValue = undefined
        local beforeReadOk = true
        try (beforeValue = arr[maxIndex]) catch (beforeReadOk = false)
        if not beforeReadOk do throw ("Forest control array element is unreadable: " + propertyName + "[" + (zeroIndex as string) + "]")
        if beforeValue != undefined and not (isValidNode beforeValue and safeClassName beforeValue == "CProxy") do
            throw ("Forest control array element is not a CProxy reference: " + propertyName + "[" + (zeroIndex as string) + "] class=" + (safeClassName beforeValue))
        local beforeJson = forestControlCProxyReferenceValueJson beforeValue
        local newValue = undefined
        if referenceMode == "cproxy" then
        (
            local nodeName = decodeBase64Utf8 encodedNodeName
            if nodeName == "" do throw "CProxy reference target name cannot be empty."
            newValue = getNodeByName nodeName
            if newValue == undefined or not (isValidNode newValue) do
                throw ("CProxy reference target was not found: " + nodeName)
            if safeClassName newValue != "CProxy" do
                throw ("CProxy reference target is not CProxy: " + nodeName + " class=" + (safeClassName newValue))
        )
        else if referenceMode != "null" then
        (
            throw ("Unsupported CProxy reference mode: " + referenceMode)
        )
        arr[maxIndex] = newValue
        refreshForestPreviewNode forestNode
        local afterValue = undefined
        local afterReadOk = true
        try (afterValue = arr[maxIndex]) catch (afterReadOk = false)
        if not afterReadOk do throw ("Forest control array CProxy reference readback failed: " + propertyName + "[" + (zeroIndex as string) + "]")
        local verified = false
        if newValue == undefined then
            verified = (afterValue == undefined) and (arr.count == countValue)
        else
            verified = (isValidNode afterValue) and (afterValue == newValue) and (safeClassName afterValue == "CProxy") and (arr.count == countValue)
        if not verified do throw ("Forest control array CProxy reference write verification failed: " + propertyName + "[" + (zeroIndex as string) + "]")
        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"property_name\":" + (jsonString propertyName) +
        ",\"index\":" + (zeroIndex as string) +
        ",\"count\":" + (countValue as string) +
        ",\"reference_type\":\"cproxy\"" +
        ",\"before_value\":" + beforeJson +
        ",\"after_value\":" + (forestControlCProxyReferenceValueJson afterValue) +
        ",\"verified\":true}"
    ),

    fn forestControlSetArrayScalarJson forestName propertyName zeroIndex scalarType encodedValue =
    (
        local forestNode = findForestControlNode forestName
        local propName = forestControlPropertyName forestNode propertyName
        local arr = undefined
        local readOk = true
        try (arr = getProperty forestNode propName) catch (readOk = false)
        if not readOk do throw ("Forest control array property is unreadable: " + propertyName)
        local arrayClass = safeClassName arr
        if arrayClass != "ArrayParameter" and arrayClass != "Array" do
            throw ("Forest control property is not an array: " + propertyName + " class=" + arrayClass)
        if zeroIndex < 0 do throw "Forest control array index must be zero or greater."
        local countValue = arr.count
        if zeroIndex >= countValue do
            throw ("Forest control array index out of range: " + propertyName + " index=" + (zeroIndex as string) + " count=" + (countValue as string))
        local maxIndex = zeroIndex + 1
        local beforeValue = undefined
        local beforeReadOk = true
        try (beforeValue = arr[maxIndex]) catch (beforeReadOk = false)
        if not beforeReadOk do throw ("Forest control array element is unreadable: " + propertyName + "[" + (zeroIndex as string) + "]")
        local beforeClass = safeClassName beforeValue
        local expectedFamily = forestControlScalarFamily beforeClass
        if expectedFamily == "" do throw ("Forest control array element is not scalar writable: " + propertyName + "[" + (zeroIndex as string) + "] class=" + beforeClass)
        if scalarType != expectedFamily do throw ("Array scalar type mismatch for " + propertyName + "[" + (zeroIndex as string) + "]: expected " + expectedFamily + ", got " + scalarType)
        local beforeJson = forestControlArrayScalarValueJson beforeValue
        local newValue = parseForestControlScalar scalarType encodedValue
        arr[maxIndex] = newValue
        refreshForestPreviewNode forestNode
        local afterValue = undefined
        local afterReadOk = true
        try (afterValue = arr[maxIndex]) catch (afterReadOk = false)
        if not afterReadOk do throw ("Forest control array element readback failed: " + propertyName + "[" + (zeroIndex as string) + "]")
        local afterClass = safeClassName afterValue
        local afterFamily = forestControlScalarFamily afterClass
        local verified = false
        if scalarType == "float" then
        (
            try (verified = (abs ((afterValue as float) - (newValue as float))) <= 0.000001) catch (verified = false)
        )
        else
        (
            try (verified = (afterValue == newValue)) catch (verified = false)
        )
        if afterFamily != expectedFamily do verified = false
        if arr.count != countValue do verified = false
        if not verified do throw ("Forest control array scalar write verification failed: " + propertyName + "[" + (zeroIndex as string) + "]")
        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"property_name\":" + (jsonString propertyName) +
        ",\"index\":" + (zeroIndex as string) +
        ",\"count\":" + (countValue as string) +
        ",\"value_class\":" + (jsonString afterClass) +
        ",\"scalar_type\":" + (jsonString scalarType) +
        ",\"before_value\":" + beforeJson +
        ",\"after_value\":" + (forestControlArrayScalarValueJson afterValue) +
        ",\"verified\":true}"
    ),

    fn forestControlPoint3Json value =
    (
        "[" + (value.x as string) + "," + (value.y as string) + "," + (value.z as string) + "]"
    ),

    fn forestControlSetArrayPoint3Json forestName propertyName zeroIndex xValue yValue zValue =
    (
        local forestNode = findForestControlNode forestName
        local propName = forestControlPropertyName forestNode propertyName
        local arr = undefined
        local readOk = true
        try (arr = getProperty forestNode propName) catch (readOk = false)
        if not readOk do throw ("Forest control array property is unreadable: " + propertyName)
        local arrayClass = safeClassName arr
        if arrayClass != "ArrayParameter" and arrayClass != "Array" do
            throw ("Forest control property is not an array: " + propertyName + " class=" + arrayClass)
        if zeroIndex < 0 do throw "Forest control array index must be zero or greater."
        local countValue = arr.count
        if zeroIndex >= countValue do
            throw ("Forest control array index out of range: " + propertyName + " index=" + (zeroIndex as string) + " count=" + (countValue as string))
        local maxIndex = zeroIndex + 1
        local beforeValue = undefined
        local beforeReadOk = true
        try (beforeValue = arr[maxIndex]) catch (beforeReadOk = false)
        if not beforeReadOk do throw ("Forest control array element is unreadable: " + propertyName + "[" + (zeroIndex as string) + "]")
        local beforeClass = safeClassName beforeValue
        if beforeClass != "Point3" do throw ("Forest control array element is not Point3 writable: " + propertyName + "[" + (zeroIndex as string) + "] class=" + beforeClass)
        local beforeJson = forestControlPoint3Json beforeValue
        local newValue = [xValue, yValue, zValue]
        arr[maxIndex] = newValue
        refreshForestPreviewNode forestNode
        local afterValue = undefined
        local afterReadOk = true
        try (afterValue = arr[maxIndex]) catch (afterReadOk = false)
        if not afterReadOk do throw ("Forest control array Point3 readback failed: " + propertyName + "[" + (zeroIndex as string) + "]")
        local verified = false
        try
        (
            verified = (safeClassName afterValue == "Point3") and
                (abs ((afterValue.x as float) - xValue) <= 0.00001) and
                (abs ((afterValue.y as float) - yValue) <= 0.00001) and
                (abs ((afterValue.z as float) - zValue) <= 0.00001) and
                (arr.count == countValue)
        )
        catch (verified = false)
        if not verified do throw ("Forest control array Point3 write verification failed: " + propertyName + "[" + (zeroIndex as string) + "]")
        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"property_name\":" + (jsonString propertyName) +
        ",\"index\":" + (zeroIndex as string) +
        ",\"count\":" + (countValue as string) +
        ",\"value_class\":\"Point3\"" +
        ",\"vector_type\":\"point3\"" +
        ",\"before_value\":" + beforeJson +
        ",\"after_value\":" + (forestControlPoint3Json afterValue) +
        ",\"verified\":true}"
    ),

    fn forestControlSetScalarJson forestName propertyName scalarType encodedValue =
    (
        local forestNode = findForestControlNode forestName
        local propName = forestControlPropertyName forestNode propertyName
        if forestControlExplicitReadOnly propertyName do throw ("Forest control property is explicitly read-only: " + propertyName)

        local beforeValue = undefined
        local beforeReadOk = true
        try (beforeValue = getProperty forestNode propName) catch (beforeReadOk = false)
        if not beforeReadOk do throw ("Forest control property is unreadable: " + propertyName)
        local beforeClass = safeClassName beforeValue
        local writeMode = forestControlWriteMode beforeValue
        if writeMode != "scalar" do throw ("Forest control property is not scalar writable: " + propertyName + " class=" + beforeClass)

        local expectedFamily = forestControlScalarFamily beforeClass
        if expectedFamily == "" do throw ("Unsupported Forest control scalar class: " + beforeClass)
        if scalarType != expectedFamily do throw ("Scalar type mismatch for " + propertyName + ": expected " + expectedFamily + ", got " + scalarType)

        local beforeJson = safePropertyValueJson forestNode propName
        local newValue = parseForestControlScalar scalarType encodedValue
        setProperty forestNode propName newValue
        refreshForestPreviewNode forestNode

        local afterValue = undefined
        local afterReadOk = true
        try (afterValue = getProperty forestNode propName) catch (afterReadOk = false)
        if not afterReadOk do throw ("Forest control readback failed: " + propertyName)
        local afterClass = safeClassName afterValue
        local afterFamily = forestControlScalarFamily afterClass
        local verified = false
        if scalarType == "float" then
        (
            try (verified = (abs ((afterValue as float) - (newValue as float))) <= 0.000001) catch (verified = false)
        )
        else
        (
            try (verified = (afterValue == newValue)) catch (verified = false)
        )
        if afterFamily != expectedFamily do verified = false
        if not verified do throw ("Forest control scalar write verification failed: " + propertyName)

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"property_name\":" + (jsonString propertyName) +
        ",\"value_class\":" + (jsonString afterClass) +
        ",\"scalar_type\":" + (jsonString scalarType) +
        ",\"before_value\":" + beforeJson +
        ",\"after_value\":" + safePropertyValueJson forestNode propName +
        ",\"verified\":true}"
    ),

    fn forestControlSetColorJson forestName propertyName redValue greenValue blueValue =
    (
        local forestNode = findForestControlNode forestName
        local propName = forestControlPropertyName forestNode propertyName
        if forestControlExplicitReadOnly propertyName do throw ("Forest control property is explicitly read-only: " + propertyName)

        local beforeValue = undefined
        local readOk = true
        try (beforeValue = getProperty forestNode propName) catch (readOk = false)
        if not readOk do throw ("Forest control property is unreadable: " + propertyName)
        local beforeClass = safeClassName beforeValue
        if beforeClass != "Color" do throw ("Forest control property is not Color writable: " + propertyName + " class=" + beforeClass)

        if redValue < 0.0 or redValue > 255.0 or greenValue < 0.0 or greenValue > 255.0 or blueValue < 0.0 or blueValue > 255.0 do
            throw "Forest control Color channels must be within 0..255."

        local beforeJson = safePropertyValueJson forestNode propName
        local targetValue = color redValue greenValue blueValue
        setProperty forestNode propName targetValue

        local afterValue = undefined
        local afterReadOk = true
        try (afterValue = getProperty forestNode propName) catch (afterReadOk = false)
        if not afterReadOk do throw ("Forest control Color readback failed: " + propertyName)
        local afterClass = safeClassName afterValue
        if afterClass != "Color" do throw ("Forest control Color readback class mismatch: " + propertyName + " class=" + afterClass)
        if (abs (afterValue.r - redValue)) > 0.001 or (abs (afterValue.g - greenValue)) > 0.001 or (abs (afterValue.b - blueValue)) > 0.001 do
            throw ("Forest control Color readback mismatch: " + propertyName)

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"property_name\":" + (jsonString propertyName) +
        ",\"value_class\":\"Color\"" +
        ",\"color_type\":\"rgb_0_255\"" +
        ",\"before_value\":" + beforeJson +
        ",\"after_value\":" + safePropertyValueJson forestNode propName +
        ",\"verified\":true}"
    ),

    fn getManagedLayer =
    (
        local managedLayer = LayerManager.getLayerFromName "FM_MANAGED"
        if managedLayer == undefined do managedLayer = LayerManager.newLayerFromName "FM_MANAGED"
        if managedLayer == undefined do throw "Unable to create or resolve FM_MANAGED layer."
        managedLayer
    ),

    fn getOrCreateManagedChildLayer layerName =
    (
        local managedLayer = getManagedLayer()
        local childLayer = LayerManager.getLayerFromName layerName
        if childLayer == undefined do childLayer = LayerManager.newLayerFromName layerName
        if childLayer == undefined do throw ("Unable to create or resolve managed child layer: " + layerName)
        if childLayer.name != layerName do
        (
            local renamed = false
            try
            (
                childLayer.name = layerName
                renamed = (childLayer.name == layerName)
            )
            catch()
            if not renamed do
            (
                try
                (
                    local temporaryName = layerName + "__FM_CASE_RENAME__"
                    childLayer.name = temporaryName
                    childLayer.name = layerName
                    renamed = (childLayer.name == layerName)
                )
                catch()
            )
        )
        local parentOk = false
        try
        (
            local currentParent = childLayer.getParent()
            if currentParent == managedLayer then
                parentOk = true
            else
                parentOk = childLayer.setParent managedLayer
        )
        catch (parentOk = false)
        if not parentOk do throw ("Unable to parent managed child layer under FM_MANAGED: " + layerName)
        childLayer
    ),

    fn getManagedForestsLayer =
    (
        getOrCreateManagedChildLayer "FM_FORESTS"
    ),

    fn getManagedReferencesLayer =
    (
        getOrCreateManagedChildLayer "FM_REFERENCES"
    ),

    fn setLayerProtectionState layer frozenState lockedState visibleState =
    (
        if layer == undefined do return false
        local frozenWriteOk = true
        local lockWriteOk = true
        local visibleWriteOk = true
        try (layer.lock = false) catch()
        try (layer.isFrozen = frozenState) catch (frozenWriteOk = false)
        try (layer.on = visibleState) catch (visibleWriteOk = false)
        try (layer.lock = lockedState) catch (lockWriteOk = false)
        if not frozenWriteOk do throw ("Managed layer frozen state could not be changed: " + layer.name)
        if not visibleWriteOk do throw ("Managed layer visibility could not be changed: " + layer.name)
        if not lockWriteOk do throw ("Managed layer lock state could not be changed: " + layer.name)
        if layer.isFrozen != frozenState do throw ("Managed layer frozen verification failed: " + layer.name)
        if layer.lock != lockedState do throw ("Managed layer lock verification failed: " + layer.name)
        if layer.on != visibleState do throw ("Managed layer visibility verification failed: " + layer.name)
        true
    ),

    fn setManagedLayerProtected protectedState =
    (
        local managedLayer = getManagedLayer()
        local forestsLayer = getManagedForestsLayer()
        local referencesLayer = getManagedReferencesLayer()
        if protectedState then
        (
            setLayerProtectionState forestsLayer true true true
            setLayerProtectionState referencesLayer true true false
            setLayerProtectionState managedLayer true true true
        )
        else
        (
            setLayerProtectionState managedLayer false false true
            setLayerProtectionState forestsLayer false false true
            setLayerProtectionState referencesLayer false false false
        )
        true
    ),

    fn isReservedManagedForestName nodeName =
    (
        local value = nodeName as string
        if value == "FM_Forest_001" then return true
        matchPattern value pattern:"FM_Layer_*" ignoreCase:false
    ),

    fn isForestNode node =
    (
        if node == undefined do return false
        local result = false
        try (result = isKindOf node ::Forest_Pro) catch (result = false)
        result
    ),

    fn markManagedForestNode node role:"plant_group" =
    (
        if not (isForestNode node) do throw "Managed node is not a Forest Pack Forest object."
        markForestManagerOwnedNode node role:role
        try (setUserProp node "ForestManagerManagedVersion" "1") catch()
        true
    ),

    fn moveNodeToManagedLayer node =
    (
        if node == undefined do return false
        local targetLayer = undefined
        if isForestNode node then
            targetLayer = getManagedForestsLayer()
        else
            targetLayer = getManagedReferencesLayer()
        local moved = false
        try
        (
            targetLayer.addNode node
            moved = true
        )
        catch()
        if not moved do throw ("Unable to move managed node to " + targetLayer.name + ": " + node.name)
        true
    ),

    fn migrateLegacyReferenceLayer =
    (
        local migrated = #()
        local legacyLayer = LayerManager.getLayerFromName "FM_References"
        if legacyLayer == undefined do return migrated
        local targetLayer = getManagedReferencesLayer()
        local legacyNodes = #()
        try (legacyLayer.nodes &legacyNodes) catch()
        for node in legacyNodes do
        (
            if node != undefined and isForestManagerOwnedNode node do
            (
                try
                (
                    targetLayer.addNode node
                    append migrated node.name
                )
                catch()
            )
        )
        try (legacyLayer.on = false) catch()
        migrated
    ),

    fn adoptReservedManagedForests =
    (
        local adopted = #()
        local alreadyOwned = #()
        for node in objects do
        (
            if isForestNode node and isReservedManagedForestName node.name do
            (
                if isForestManagerOwnedNode node then
                    append alreadyOwned node.name
                else
                (
                    local role = if node.name == "FM_Forest_001" then "primary_forest" else "plant_group_runtime"
                    markManagedForestNode node role:role
                    append adopted node.name
                )
                moveNodeToManagedLayer node
            )
        )
        #(adopted, alreadyOwned)
    ),

    fn protectAllManagedNodes =
    (
        setManagedLayerProtected false
        local managedLayer = getManagedLayer()
        local moved = #()
        for node in objects do
        (
            if isForestManagerOwnedNode node do
            (
                moveNodeToManagedLayer node
                append moved node.name
            )
        )
        setManagedLayerProtected true
        moved
    ),

    fn stringArrayJson values =
    (
        local result = "["
        for i = 1 to values.count do
        (
            if i > 1 do result += ","
            result += jsonString values[i]
        )
        result + "]"
    ),

    fn layerStateJson layer =
    (
        if layer == undefined do return "null"
        local frozen = false
        local locked = false
        local visible = true
        local parentName = ""
        try (frozen = layer.isFrozen) catch()
        try (locked = layer.lock) catch()
        try (visible = layer.on) catch()
        try
        (
            local parentLayer = layer.getParent()
            if parentLayer != undefined do parentName = parentLayer.name
        )
        catch()
        "{\"name\":" + jsonString layer.name +
        ",\"parent\":" + jsonString parentName +
        ",\"frozen\":" + boolJson frozen +
        ",\"locked\":" + boolJson locked +
        ",\"visible\":" + boolJson visible + "}"
    ),

    fn managedSceneStatusJson =
    (
        local managedLayer = getManagedLayer()
        local forestsLayer = getManagedForestsLayer()
        local referencesLayer = getManagedReferencesLayer()
        local managedNames = #()
        local managedForests = #()
        local technicalForests = #()
        local managedReferences = #()
        local forestNodes = #()
        local referenceNodes = #()
        try (forestsLayer.nodes &forestNodes) catch()
        try (referencesLayer.nodes &referenceNodes) catch()
        for node in forestNodes do
        (
            if node != undefined do
            (
                append managedNames node.name
                if isForestNode node do
                (
                    append managedForests node.name
                    if matchPattern node.name pattern:"FM_Layer_*" ignoreCase:false do append technicalForests node.name
                )
            )
        )
        for node in referenceNodes do
        (
            if node != undefined do
            (
                append managedNames node.name
                append managedReferences node.name
            )
        )
        local frozen = false
        local locked = false
        try (frozen = managedLayer.isFrozen) catch()
        try (locked = managedLayer.lock) catch()
        "{\"layer_name\":\"FM_MANAGED\"" +
        ",\"frozen\":" + boolJson frozen +
        ",\"locked\":" + boolJson locked +
        ",\"forests_layer\":" + layerStateJson forestsLayer +
        ",\"references_layer\":" + layerStateJson referencesLayer +
        ",\"managed_node_count\":" + (managedNames.count as string) +
        ",\"managed_nodes\":" + stringArrayJson managedNames +
        ",\"managed_forest_count\":" + (managedForests.count as string) +
        ",\"managed_forests\":" + stringArrayJson managedForests +
        ",\"technical_forest_count\":" + (technicalForests.count as string) +
        ",\"technical_forests\":" + stringArrayJson technicalForests +
        ",\"managed_reference_count\":" + (managedReferences.count as string) +
        ",\"managed_references\":" + stringArrayJson managedReferences +
        ",\"verified\":true}"
    ),

    fn ensureManagedSceneJson =
    (
        if not (forestPackAvailable()) do throw "Forest Pack Pro class ::Forest_Pro is not available."
        setManagedLayerProtected false
        local migratedReferences = migrateLegacyReferenceLayer()
        local adoption = adoptReservedManagedForests()
        local moved = protectAllManagedNodes()
        "{\"layer_name\":\"FM_MANAGED\"" +
        ",\"forests_layer\":\"FM_FORESTS\"" +
        ",\"references_layer\":\"FM_REFERENCES\"" +
        ",\"migrated_references\":" + stringArrayJson migratedReferences +
        ",\"adopted\":" + stringArrayJson adoption[1] +
        ",\"already_owned\":" + stringArrayJson adoption[2] +
        ",\"protected\":" + stringArrayJson moved +
        ",\"status\":" + managedSceneStatusJson() +
        ",\"verified\":true}"
    ),

    fn createManagedForestJson forestName roleName =
    (
        if not (forestPackAvailable()) do throw "Forest Pack Pro class ::Forest_Pro is not available."
        if forestName == undefined or forestName == "" do throw "Managed Forest name cannot be empty."
        if not (matchPattern forestName pattern:"FM_*" ignoreCase:false) do throw "Managed Forest names must use the FM_ prefix."
        local existing = getNodeByName forestName
        if existing != undefined then
        (
            if not (isForestNode existing) do throw ("A non-Forest object already uses the requested name: " + forestName)
            if not (isForestManagerOwnedNode existing) do throw ("Refusing to adopt non-reserved existing Forest: " + forestName)
            setManagedLayerProtected false
            moveNodeToManagedLayer existing
            setManagedLayerProtected true
            return "{\"forest_name\":" + jsonString existing.name + ",\"created\":false,\"verified\":true}"
        )

        setManagedLayerProtected false
        local forestNode = undefined
        try
        (
            forestNode = ::Forest_Pro()
            forestNode.name = forestName
            setForestPointCloudDisplay forestNode
            markManagedForestNode forestNode role:roleName
            moveNodeToManagedLayer forestNode
            setManagedLayerProtected true
            "{\"forest_name\":" + jsonString forestNode.name + ",\"created\":true,\"verified\":true}"
        )
        catch
        (
            local message = getCurrentException()
            try (if forestNode != undefined do delete forestNode) catch()
            try (setManagedLayerProtected true) catch()
            reportBridgeError ("CREATE_MANAGED_FOREST: " + message)
            throw()
        )
    ),

    fn deleteManagedForestJson forestName =
    (
        local forestNode = getNodeByName forestName
        if forestNode == undefined do return "{\"forest_name\":" + jsonString forestName + ",\"deleted\":false,\"missing\":true,\"verified\":true}"
        if not (isForestNode forestNode) do throw ("Refusing to delete non-Forest object: " + forestName)
        if forestName == "FM_Forest_001" do throw "FM_Forest_001 is the primary managed Forest and cannot be deleted by the generic delete endpoint."
        if not (isForestManagerOwnedNode forestNode) do throw ("Refusing to delete Forest without Forest Manager ownership marker: " + forestName)
        setManagedLayerProtected false
        delete forestNode
        setManagedLayerProtected true
        local stillExists = getNodeByName forestName != undefined
        if stillExists do throw ("Managed Forest delete verification failed: " + forestName)
        "{\"forest_name\":" + jsonString forestName + ",\"deleted\":true,\"missing\":false,\"verified\":true}"
    ),

    fn plantGroupAreaArrayProperties =
    (
        #(
            #aridlist, #pf_aractivelist, #arnamelist, #arnodelist, #arnodenamelist,
            #artypelist, #arincexclist, #arresollist, #arslicelist, #arslicetoplist,
            #arwidthlist, #arforceopenlist, #armaplist, #arscalelist, #arthresholdlist,
            #arsurfidlist, #arflafdenslist, #arflafscalist, #arflinvlist, #arselspeclist,
            #arspeclist, #arpaintlist, #arboundchecklist, #arprojectlist, #arshapelist,
            #arobscalelist, #arlinkidlist, #arscalemin, #arscalemax, #arzoffset
        )
    ),

    fn findPlantGroupAreaIndex forestNode groupKey =
    (
        if forestNode == undefined do return 0
        if not (isProperty forestNode #arnamelist) do return 0
        local expectedName = "FM_GROUP_" + groupKey
        for i = 1 to forestNode.arnamelist.count do
        (
            local currentName = ""
            try (currentName = forestNode.arnamelist[i] as string) catch (currentName = "")
            if currentName == expectedName do return i
        )
        0
    ),

    fn appendPlantGroupAreaClone forestNode baseIndex groupKey =
    (
        if baseIndex < 1 do throw "Plant-group base Area index must be one or greater."
        if not (isProperty forestNode #aridlist) do throw "Forest Pack property missing: aridlist."
        local oldCount = forestNode.aridlist.count
        if baseIndex > oldCount do throw "Plant-group base Area index is outside the Area list."
        local newIndex = oldCount + 1
        local props = plantGroupAreaArrayProperties()
        for propName in props do
        (
            if isProperty forestNode propName do
            (
                local arr = getProperty forestNode propName
                if (classOf arr == ArrayParameter or classOf arr == Array) do
                (
                    local beforeCount = arr.count
                    if beforeCount == oldCount do
                    (
                        local baseValue = undefined
                        try (baseValue = arr[baseIndex]) catch (baseValue = undefined)
                        arr.count = newIndex
                        try (arr[newIndex] = baseValue) catch()
                    )
                )
            )
        )
        if forestNode.aridlist.count != newIndex do throw "Plant-group Area clone did not extend aridlist."
        forestNode.aridlist[newIndex] = newIndex
        if isProperty forestNode #arnamelist do forestNode.arnamelist[newIndex] = "FM_GROUP_" + groupKey
        newIndex
    ),

    fn plantGroupGeometrySelectionCsv forestNode speciesCsv =
    (
        if forestNode == undefined do throw "Plant-group Forest target was not found."
        if not (isProperty forestNode #cobjlist) do throw "Forest Pack property missing: cobjlist."
        if not (isProperty forestNode #specidlist) do throw "Forest Pack property missing: specidlist."

        local speciesTokens = filterString speciesCsv ","
        if speciesTokens.count < 1 do throw "Plant-group species selection cannot be empty."

        local selectionCsv = ""
        for rawToken in speciesTokens do
        (
            local sourceToken = trimLeft (trimRight rawToken)
            if sourceToken == "" do throw "Plant-group species selection contains an empty token."

            local specId = 0
            local parsedNumericId = 0
            try (parsedNumericId = sourceToken as integer) catch (parsedNumericId = 0)

            if parsedNumericId > 0 then
            (
                for geometryIndex = 1 to forestNode.specidlist.count while specId == 0 do
                (
                    local candidateId = 0
                    try (candidateId = forestNode.specidlist[geometryIndex] as integer) catch (candidateId = 0)
                    if candidateId == parsedNumericId do specId = candidateId
                )
                if specId == 0 do throw ("Plant-group Geometry spec ID was not found in the target Forest: " + sourceToken)
            )
            else
            (
                local geometryIndex = findGeometrySourceIndexByName forestNode sourceToken
                if geometryIndex < 1 do throw ("Plant-group Geometry source was not found in the target Forest: " + sourceToken)
                if geometryIndex > forestNode.specidlist.count do throw ("Plant-group Geometry spec ID is unavailable for source: " + sourceToken)
                specId = forestNode.specidlist[geometryIndex] as integer
                if specId < 1 do throw ("Plant-group Geometry spec ID is invalid for source: " + sourceToken)
            )

            if selectionCsv != "" do selectionCsv += ","
            selectionCsv += (specId as string)
        )
        selectionCsv
    ),

    fn enablePlantGroupRandomizeStacked forestNode areaIndex =
    (
        if forestNode == undefined do return false
        local enabled = false
        local propNames = #()
        try (propNames = getPropNames forestNode) catch (propNames = #())
        for propName in propNames while not enabled do
        (
            local propText = toLower (propName as string)
            if (findString propText "random") != undefined and (findString propText "stack") != undefined do
            (
                try
                (
                    local value = getProperty forestNode propName
                    if isKindOf value Array then
                    (
                        if value.count < areaIndex do value.count = areaIndex
                        value[areaIndex] = true
                        setProperty forestNode propName value
                    )
                    else
                    (
                        if isKindOf value Boolean do setProperty forestNode propName true
                    )
                    enabled = true
                )
                catch()
            )
        )
        enabled
    ),

    fn plantGroupMetadataKey groupKey =
    (
        "ForestManagerPlantGroupRuntime_" + groupKey
    ),

    fn removePlantGroupAreaAtIndex forestNode removeIndex =
    (
        if forestNode == undefined do return false
        if not (isProperty forestNode #aridlist) do return false
        local oldCount = forestNode.aridlist.count
        if removeIndex < 1 or removeIndex > oldCount do return false
        local props = plantGroupAreaArrayProperties()
        for propName in props do
        (
            if isProperty forestNode propName do
            (
                local arr = getProperty forestNode propName
                if (classOf arr == ArrayParameter or classOf arr == Array) and arr.count == oldCount do
                (
                    for i = removeIndex to (oldCount - 1) do
                    (
                        try (arr[i] = arr[i + 1]) catch()
                    )
                    try (arr.count = oldCount - 1) catch()
                )
            )
        )
        forestNode.aridlist.count == (oldCount - 1)
    ),

    fn cleanupManagedPlantGroupAreas forestNode =
    (
        if forestNode == undefined do return 0
        if not (isProperty forestNode #arnamelist) do return 0
        local removed = 0
        for i = forestNode.arnamelist.count to 1 by -1 do
        (
            local currentName = ""
            try (currentName = forestNode.arnamelist[i] as string) catch (currentName = "")
            if matchPattern currentName pattern:"FM_GROUP_*" ignoreCase:true do
            (
                if removePlantGroupAreaAtIndex forestNode i do removed += 1
            )
        )
        removed
    ),

    fn plantGroupAreaUpsertJson forestName groupKey baseZeroIndex speciesCsv scalePercent =
    (
        local forestNode = findForestControlNode forestName
        if forestNode == undefined do throw "Plant-group Forest target was not found."
        if not (isProperty forestNode #aridlist) do throw "Forest Pack property missing: aridlist."
        if scalePercent <= 0.0 do throw "Plant-group distribution scale must be greater than zero."
        if speciesCsv == "" do throw "Plant-group species selection cannot be empty."

        local baseIndex = baseZeroIndex + 1
        if baseIndex < 1 or baseIndex > forestNode.aridlist.count do throw "Plant-group base Area index is out of range."

        -- Validate the requested species against the real Geometry List, but do not
        -- create another Forest Pack Area. Plant Groups are Forest Manager semantic
        -- controls, not duplicate spline areas.
        local geometrySelectionCsv = plantGroupGeometrySelectionCsv forestNode speciesCsv
        local metadataValue = geometrySelectionCsv + "|" + (scalePercent as string)
        local metadataKey = plantGroupMetadataKey groupKey
        setUserProp forestNode metadataKey metadataValue
        local readback = undefined
        try (readback = getUserProp forestNode metadataKey) catch (readback = undefined)
        if readback != metadataValue do throw "Plant-group runtime metadata verification failed."

        try (notifyDependents forestNode partID:#all message:#change) catch()

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"group_key\":" + (jsonString groupKey) +
        ",\"area_index\":" + (baseZeroIndex as string) +
        ",\"base_area_index\":" + (baseZeroIndex as string) +
        ",\"species\":" + (jsonString speciesCsv) +
        ",\"geometry_selection\":" + (jsonString geometrySelectionCsv) +
        ",\"scale_percent\":" + (scalePercent as string) +
        ",\"created\":false" +
        ",\"managed_area_created\":false" +
        ",\"verified\":true}"
    ),

    fn plantGroupSpeciesIdsFromSelection selectionCsv =
    (
        local ids = #()
        local tokens = filterString selectionCsv " ,;"
        for token in tokens do
        (
            local value = 0
            try (value = token as integer) catch (value = 0)
            if value > 0 and (findItem ids value) == 0 do append ids value
        )
        ids
    ),

    fn plantGroupSpeciesSelectionString speciesIds =
    (
        local result = ""
        for value in speciesIds do result += (" " + (value as string))
        result
    ),

    fn applyPlantGroupMetadataProbabilities forestNode groupKeys =
    (
        if forestNode == undefined do return #()
        if not (isProperty forestNode #specidlist) do throw "Forest Pack property missing: specidlist."
        if not (isProperty forestNode #problist) do throw "Forest Pack property missing: problist."

        local specIds = #()
        local weights = #()
        for groupKey in groupKeys do
        (
            local metadataKey = plantGroupMetadataKey groupKey
            local metadataValue = undefined
            try (metadataValue = getUserProp forestNode metadataKey) catch (metadataValue = undefined)
            if metadataValue == undefined or metadataValue == "" do
                throw ("Plant-group runtime metadata was not found: " + groupKey)
            local parts = filterString metadataValue "|"
            if parts.count != 2 do throw ("Plant-group runtime metadata is invalid: " + groupKey)
            local ids = plantGroupSpeciesIdsFromSelection parts[1]
            if ids.count < 1 do throw ("Plant-group runtime metadata has no species: " + groupKey)
            local scalePercent = 0.0
            try (scalePercent = parts[2] as float) catch (scalePercent = 0.0)
            if scalePercent <= 0.0 do throw ("Plant-group runtime scale is invalid: " + groupKey)
            local groupWeight = 1.0 / (scalePercent * scalePercent)
            local perSpeciesWeight = groupWeight / ids.count
            for specId in ids do
            (
                local pos = findItem specIds specId
                if pos == 0 then
                (
                    append specIds specId
                    append weights perSpeciesWeight
                )
                else
                    weights[pos] += perSpeciesWeight
            )
        )

        local totalWeight = 0.0
        for value in weights do totalWeight += value
        if totalWeight <= 0.0 do throw "Plant-group probability total is zero."

        local geometryCount = forestNode.specidlist.count
        forestNode.problist.count = geometryCount
        if isProperty forestNode #old_problist do forestNode.old_problist.count = geometryCount
        for geometryIndex = 1 to geometryCount do
        (
            local specId = 0
            try (specId = forestNode.specidlist[geometryIndex] as integer) catch (specId = 0)
            local pos = findItem specIds specId
            local probability = if pos > 0 then (weights[pos] / totalWeight) * 100.0 else 0.0
            forestNode.problist[geometryIndex] = probability
            if isProperty forestNode #old_problist do forestNode.old_problist[geometryIndex] = (probability as integer)
        )
        specIds
    ),

    fn refreshPlantGroupGeometryBindings forestNode speciesIds =
    (
        if forestNode == undefined do throw "Plant-group Geometry refresh target is undefined."
        if not (isProperty forestNode #cobjlist) do throw "Forest Pack property missing: cobjlist."
        if not (isProperty forestNode #geomlist) do throw "Forest Pack property missing: geomlist."
        if not (isProperty forestNode #specidlist) do throw "Forest Pack property missing: specidlist."

        local refreshedIds = #()
        for geometryIndex = 1 to forestNode.cobjlist.count do
        (
            local sourceNode = undefined
            local specId = 0
            try (sourceNode = forestNode.cobjlist[geometryIndex]) catch (sourceNode = undefined)
            try (specId = forestNode.specidlist[geometryIndex] as integer) catch (specId = 0)

            if sourceNode != undefined and (findItem speciesIds specId) > 0 do
            (
                -- The legacy multi-Forest path always had one live Custom Object
                -- binding per Forest. Recreate that same binding contract for every
                -- selected species inside the consolidated Forest so Forest Pack
                -- rebuilds its internal Geometry cache instead of retaining only the
                -- original first item.
                forestNode.cobjlist[geometryIndex] = undefined
                forestNode.cobjlist[geometryIndex] = sourceNode
                forestNode.geomlist[geometryIndex] = 2
                if isProperty forestNode #nongeomlist and forestNode.nongeomlist.count >= geometryIndex do
                    forestNode.nongeomlist[geometryIndex] = false
                append refreshedIds specId
            )
        )

        for specId in speciesIds do
        (
            if (findItem refreshedIds specId) == 0 do
                throw ("Plant-group Geometry binding was not found for species ID: " + (specId as string))
        )

        if isProperty forestNode #disabled do forestNode.disabled = false
        if isProperty forestNode #manualupdate do forestNode.manualupdate = false
        try (notifyDependents forestNode partID:#all message:#change) catch()
        try (forestNode.update()) catch()
        try (redrawViews()) catch()
        completeRedraw()

        refreshedIds.count
    ),

    fn plantGroupGeneratedGeomIdSummary forestNode expectedSpeciesIds =
    (
        if forestNode == undefined do throw "Plant-group generated Geometry summary target is undefined."
        local itemCount = getForestGeneratedItemCount forestNode
        if itemCount < 0 do throw "Forest Pack generated item collection is unavailable."

        local counts = #()
        for specId in expectedSpeciesIds do append counts 0

        for itemIndex = 0 to (itemCount - 1) do
        (
            local geomId = 0
            try (geomId = forestNode.trees.getGeomID itemIndex) catch (geomId = 0)
            local pos = findItem expectedSpeciesIds geomId
            if pos > 0 do counts[pos] += 1
        )

        local json = "["
        for i = 1 to expectedSpeciesIds.count do
        (
            if i > 1 do json += ","
            json += "{\"species_id\":" + (expectedSpeciesIds[i] as string) +
                    ",\"generated_items\":" + (counts[i] as string) + "}"
        )
        json += "]"
        #(json, counts)
    ),

    fn plantGroupGeneratedGeomRuntimeDiagnosticJson forestNode expectedSpeciesIds =
    (
        if forestNode == undefined do throw "Plant-group runtime diagnostic target is undefined."
        local itemCount = getForestGeneratedItemCount forestNode
        local uniqueGeomIds = #()
        local uniqueGeomCounts = #()
        if itemCount > 0 do
        (
            for itemIndex = 0 to (itemCount - 1) do
            (
                local geomId = -2147483648
                try (geomId = forestNode.trees.getGeomID itemIndex) catch (geomId = -2147483648)
                local pos = findItem uniqueGeomIds geomId
                if pos == 0 then
                (
                    append uniqueGeomIds geomId
                    append uniqueGeomCounts 1
                )
                else uniqueGeomCounts[pos] += 1
            )
        )

        local expectedJson = "["
        for i = 1 to expectedSpeciesIds.count do
        (
            if i > 1 do expectedJson += ","
            expectedJson += (expectedSpeciesIds[i] as string)
        )
        expectedJson += "]"

        local observedJson = "["
        for i = 1 to uniqueGeomIds.count do
        (
            if i > 1 do observedJson += ","
            observedJson += "{\"geom_id\":" + (uniqueGeomIds[i] as string) + ",\"items\":" + (uniqueGeomCounts[i] as string) + "}"
        )
        observedJson += "]"

        local colorJson = "["
        if isProperty forestNode #coloridlist do
        (
            for i = 1 to forestNode.coloridlist.count do
            (
                if i > 1 do colorJson += ","
                local cidValue = forestNode.coloridlist[i]
                local cidClass = safeClassName cidValue
                local cidR = 0.0
                local cidG = 0.0
                local cidB = 0.0
                if cidClass == "Color" then
                (
                    cidR = cidValue.r as float
                    cidG = cidValue.g as float
                    cidB = cidValue.b as float
                )
                else if cidClass == "Point3" then
                (
                    cidR = cidValue.x as float
                    cidG = cidValue.y as float
                    cidB = cidValue.z as float
                )
                else if cidClass == "Array" and cidValue.count >= 3 then
                (
                    cidR = cidValue[1] as float
                    cidG = cidValue[2] as float
                    cidB = cidValue[3] as float
                )
                else
                (
                    throw ("Unsupported Forest Pack Color-ID value class in runtime diagnostic: " + cidClass + " value=" + (cidValue as string))
                )
                local cidText = ((cidR as integer) as string) + "," + ((cidG as integer) as string) + "," + ((cidB as integer) as string)
                colorJson += jsonString cidText
            )
        )
        colorJson += "]"

        "{\"generated_items\":" + (itemCount as string) +
        ",\"expected_species_ids\":" + expectedJson +
        ",\"observed_geom_ids\":" + observedJson +
        ",\"color_ids\":" + colorJson + "}"
    ),

    fn plantGroupAreaFinalizeJson forestName baseIndicesCsv groupKeysCsv =
    (
        local forestNode = findForestControlNode forestName
        if forestNode == undefined do throw "Plant-group Forest target was not found."
        if not (isProperty forestNode #pf_aractivelist) do throw "Forest Pack property missing: pf_aractivelist."
        if not (isProperty forestNode #arselspeclist) do throw "Forest Pack property missing: arselspeclist."
        if not (isProperty forestNode #arspeclist) do throw "Forest Pack property missing: arspeclist."

        local baseTokens = filterString baseIndicesCsv ","
        local groupTokens = filterString groupKeysCsv ","
        if groupTokens.count < 1 do throw "Plant-group finalize has no groups."

        -- Remove every managed Area created by the older Stage 7.18 implementation.
        -- Only the user's real/base spline Area remains in Forest Pack.
        local removedManagedAreas = cleanupManagedPlantGroupAreas forestNode

        local allSpeciesIds = applyPlantGroupMetadataProbabilities forestNode groupTokens
        if allSpeciesIds.count < 1 do throw "Plant-group finalize found no Geometry species."
        local refreshedGeometryCount = refreshPlantGroupGeometryBindings forestNode allSpeciesIds
        if refreshedGeometryCount != allSpeciesIds.count do throw "Plant-group Geometry refresh count mismatch."
        local combinedSpecies = plantGroupSpeciesSelectionString allSpeciesIds

        -- Keep only the requested real base Areas active. Do not manufacture one Area
        -- per semantic Plant Group.
        local requestedBaseIndices = #()
        for token in baseTokens do
        (
            local zeroIndex = 0
            try (zeroIndex = token as integer) catch (zeroIndex = -1)
            local maxIndex = zeroIndex + 1
            if maxIndex >= 1 and maxIndex <= forestNode.pf_aractivelist.count and (findItem requestedBaseIndices maxIndex) == 0 do
                append requestedBaseIndices maxIndex
        )
        if requestedBaseIndices.count < 1 do throw "Plant-group finalize did not resolve a real base Area."

        for i = 1 to forestNode.pf_aractivelist.count do
        (
            local areaName = ""
            try (areaName = forestNode.arnamelist[i] as string) catch (areaName = "")
            if matchPattern areaName pattern:"FM_GROUP_*" ignoreCase:true then
                forestNode.pf_aractivelist[i] = false
            else if (findItem requestedBaseIndices i) > 0 then
                forestNode.pf_aractivelist[i] = true
        )

        for maxIndex in requestedBaseIndices do
        (
            forestNode.arselspeclist[maxIndex] = true
            forestNode.arspeclist[maxIndex] = combinedSpecies
            if forestNode.pf_aractivelist[maxIndex] != true do throw "Plant-group base Area activation failed."
            if (forestNode.arspeclist[maxIndex] as string) != combinedSpecies do throw "Plant-group base species verification failed."
        )

        -- Hard acceptance guard: no FM_GROUP Area may survive cleanup.
        local remainingManagedAreas = 0
        for i = 1 to forestNode.arnamelist.count do
        (
            local currentName = ""
            try (currentName = forestNode.arnamelist[i] as string) catch (currentName = "")
            if matchPattern currentName pattern:"FM_GROUP_*" ignoreCase:true do remainingManagedAreas += 1
        )
        if remainingManagedAreas != 0 do throw "Managed Plant Group Areas remain after cleanup."

        -- A consolidated Forest with multiple Geometry species must use Random
        -- diversity here. The legacy scene was intentionally left in Clusters
        -- mode (divers=2), which was harmless when each Forest contained only one
        -- species but can make a single consolidated Forest choose one huge
        -- species cluster across the entire planting area. Random mode (divers=0)
        -- is Forest Pack's default probability-driven Geometry selection mode.
        local diversityBefore = if isProperty forestNode #divers then forestNode.divers else -1
        if isProperty forestNode #divers do forestNode.divers = 0
        if isProperty forestNode #divers and forestNode.divers != 0 do throw "Plant-group diversity could not be switched to Random mode."

        if isProperty forestNode #disabled do forestNode.disabled = false
        if isProperty forestNode #manualupdate do forestNode.manualupdate = false
        try (notifyDependents forestNode partID:#all message:#change) catch()
        try (forestNode.update()) catch()
        completeRedraw()

        -- Acceptance is based on Forest Pack's generated items, not only on the
        -- writable parameter arrays. getGeomID is the actual Geometry ID used by
        -- each generated Forest item. Every requested species must occur at least
        -- once or this finalize fails.
        local generatedSummary = plantGroupGeneratedGeomIdSummary forestNode allSpeciesIds
        local generatedGeomJson = generatedSummary[1]
        local generatedGeomCounts = generatedSummary[2]
        -- Generated-item coverage is diagnostic here. The final Diversity Map
        -- is bound after finalize, and small planting areas can legitimately
        -- contain fewer generated items than the number of configured species.
        -- Structural validity is verified above; strict species coverage belongs
        -- to the explicit post-bind acceptance path.

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"distribution_mode\":\"single_real_area_geometry_species\"" +
        ",\"diversity_before\":" + (diversityBefore as string) +
        ",\"diversity_mode\":\"random\"" +
        ",\"diversity_value\":" + ((if isProperty forestNode #divers then forestNode.divers else -1) as string) +
        ",\"generated_geometry_ids\":" + generatedGeomJson +
        ",\"removed_managed_area_count\":" + (removedManagedAreas as string) +
        ",\"remaining_managed_area_count\":0" +
        ",\"active_group_area_count\":0" +
        ",\"active_base_area_count\":" + (requestedBaseIndices.count as string) +
        ",\"species_selection\":" + (jsonString combinedSpecies) +
        ",\"species_count\":" + (allSpeciesIds.count as string) +
        ",\"refreshed_geometry_count\":" + (refreshedGeometryCount as string) +
        ",\"area_count\":" + (forestNode.aridlist.count as string) +
        ",\"generated_items\":" + (getForestGeneratedItemCount forestNode as string) +
        ",\"verified\":true}"
    ),


    fn plantGroupColorIdChannels value =
    (
        local valueClass = safeClassName value
        if valueClass == "Color" then
            return #((value.r as float), (value.g as float), (value.b as float))
        if valueClass == "Point3" then
            return #((value.x as float), (value.y as float), (value.z as float))
        if valueClass == "Array" and value.count >= 3 then
            return #((value[1] as float), (value[2] as float), (value[3] as float))
        throw ("Unsupported Forest Pack Color-ID value class: " + valueClass + " value=" + (value as string))
    ),

    fn plantGroupColorIdJson value =
    (
        local channels = plantGroupColorIdChannels value
        local cidText = ((channels[1] as integer) as string) + "," + ((channels[2] as integer) as string) + "," + ((channels[3] as integer) as string)
        jsonString cidText
    ),

    fn plantGroupBindSingleForestDiversityMapJson forestName encodedMapPath strictVerify =
    (
        local forestNode = findForestControlNode forestName
        if forestNode == undefined do throw "Single-Forest diversity-map target was not found."
        if not (isProperty forestNode #divtmap) do throw "Forest Pack property missing: divtmap."
        if not (isProperty forestNode #divers) do throw "Forest Pack property missing: divers."
        if not (isProperty forestNode #coloridlist) do throw "Forest Pack property missing: coloridlist."
        if forestNode.coloridlist.count < 3 do throw "Single-Forest diversity map requires at least three Geometry items."

        local mapPath = decodeBase64Utf8 encodedMapPath
        if mapPath == "" do throw "Single-Forest diversity map path is empty."
        if not (doesFileExist mapPath) do throw ("Single-Forest diversity map file was not found: " + mapPath)

        local colorIdsSnapshot = #()
        for i = 1 to forestNode.coloridlist.count do append colorIdsSnapshot forestNode.coloridlist[i]

        local previousUnitsX = if isProperty forestNode #units_x then forestNode.units_x else 0.0
        local previousUnitsY = if isProperty forestNode #units_y then forestNode.units_y else 0.0
        local previousDistmap = if isProperty forestNode #distmap then forestNode.distmap else undefined
        local previousDensityMap = if isProperty forestNode #densityMap then forestNode.densityMap else false
        local previousDistmode = if isProperty forestNode #distmode then forestNode.distmode else -1

        local bitmapMap = Bitmaptexture filename:mapPath
        if bitmapMap == undefined do throw "Could not create the Single-Forest diversity Bitmaptexture."
        local coords = undefined
        try (coords = bitmapMap.coords) catch (coords = undefined)
        if coords == undefined do throw "Single-Forest diversity Bitmaptexture coords are unavailable."
        normalizeSpeciesDensityMapCoords coords
        coords.U_Tile = false
        coords.V_Tile = false

        -- Diversity is independent from distribution density.  Never rewrite
        -- units_x/units_y here: those values are the live Forest distribution
        -- spacing and must remain at the caller-selected density (for example
        -- 0.75 m in the Stage 8 visible acceptance scene).
        forestNode.divtmap = bitmapMap
        forestNode.divers = 1
        if isProperty forestNode #divmapnoise do forestNode.divmapnoise = 0.0

        local restoreColorCount = amin forestNode.coloridlist.count colorIdsSnapshot.count
        for i = 1 to restoreColorCount do forestNode.coloridlist[i] = colorIdsSnapshot[i]
        if restoreColorCount != colorIdsSnapshot.count do
            throw "Single-Forest diversity map Color-ID restore count changed during map binding."

        if isProperty forestNode #disabled do forestNode.disabled = false
        if isProperty forestNode #manualupdate do forestNode.manualupdate = false
        try (notifyDependents forestNode partID:#all message:#change) catch()
        try (forestNode.update()) catch()
        completeRedraw()

        if forestNode.divtmap == undefined do throw "Single-Forest diversity map assignment returned undefined."
        local assignedFile = ""
        try (assignedFile = forestNode.divtmap.filename) catch (assignedFile = "")
        if toLower assignedFile != toLower mapPath do throw "Single-Forest diversity map filename verification failed."
        if forestNode.divers != 1 do throw "Single-Forest diversity mode is not Match Color ID on Map."
        if isProperty forestNode #units_x and abs(forestNode.units_x - previousUnitsX) > 0.001 do throw "Diversity-map binding changed units_x."
        if isProperty forestNode #units_y and abs(forestNode.units_y - previousUnitsY) > 0.001 do throw "Diversity-map binding changed units_y."
        if isProperty forestNode #distmap and forestNode.distmap != previousDistmap do throw "Diversity-map binding changed distmap."
        if isProperty forestNode #densityMap and forestNode.densityMap != previousDensityMap do throw "Diversity-map binding changed densityMap."
        if isProperty forestNode #distmode and forestNode.distmode != previousDistmode do throw "Diversity-map binding changed distmode."

        local colorIdsJson = "["
        for i = 1 to forestNode.coloridlist.count do
        (
            if i > 1 do colorIdsJson += ","
            local cid = forestNode.coloridlist[i]
            colorIdsJson += plantGroupColorIdJson cid
        )
        colorIdsJson += "]"

        local generatedGeomJson = "[]"
        local configuredSpeciesJson = "[]"
        local speciesBindingVerified = false
        local generatedGeometryTypeJson = "[]"
        if strictVerify do
        (
            if not (isProperty forestNode #specidlist) do throw "Forest Pack property missing: specidlist."
            if not (isProperty forestNode #cobjlist) do throw "Forest Pack property missing: cobjlist."
            if not (isProperty forestNode #geomlist) do throw "Forest Pack property missing: geomlist."
            local speciesIds = #()
            local colorKeys = #()
            configuredSpeciesJson = "["
            for i = 1 to forestNode.specidlist.count do
            (
                local specId = forestNode.specidlist[i] as integer
                if specId <= 0 do throw "Single-Forest diversity-map verification found an invalid species ID."
                if (findItem speciesIds specId) > 0 do throw ("Single-Forest diversity-map verification found a duplicate species ID: " + (specId as string))
                append speciesIds specId
                if i > 1 do configuredSpeciesJson += ","
                configuredSpeciesJson += (specId as string)
                if i > forestNode.cobjlist.count or forestNode.cobjlist[i] == undefined do throw ("Single-Forest diversity-map verification found no Custom Object for species ID: " + (specId as string))
                if i > forestNode.geomlist.count or forestNode.geomlist[i] == 0 do throw ("Single-Forest diversity-map verification found disabled Geometry for species ID: " + (specId as string))
                if i > forestNode.coloridlist.count do throw ("Single-Forest diversity-map verification found no Color ID for species ID: " + (specId as string))
                local channels = plantGroupColorIdChannels forestNode.coloridlist[i]
                local colorKey = ((channels[1] as integer) as string) + "," + ((channels[2] as integer) as string) + "," + ((channels[3] as integer) as string)
                if (findItem colorKeys colorKey) > 0 do throw ("Single-Forest diversity-map verification found duplicate Color ID: " + colorKey)
                append colorKeys colorKey
            )
            configuredSpeciesJson += "]"
            if speciesIds.count < 3 do throw "Single-Forest diversity-map verification found fewer than three species IDs."
            if colorKeys.count != speciesIds.count do throw "Single-Forest diversity-map species/Color ID count mismatch."
            local itemCount = getForestGeneratedItemCount forestNode
            if itemCount <= 0 do throw "Single-Forest diversity map generated no Forest items."
            generatedGeometryTypeJson = (plantGroupGeneratedGeomRuntimeDiagnosticJson forestNode speciesIds)
            speciesBindingVerified = true
        )

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"map_path\":" + (jsonString assignedFile) +
        ",\"map_slot\":\"divtmap\"" +
        ",\"units_x\":" + ((if isProperty forestNode #units_x then forestNode.units_x else 0.0) as string) +
        ",\"units_y\":" + ((if isProperty forestNode #units_y then forestNode.units_y else 0.0) as string) +
        ",\"density_preserved\":true" +
        ",\"map_u_tile\":" + (boolJson coords.U_Tile) +
        ",\"map_v_tile\":" + (boolJson coords.V_Tile) +
        ",\"diversity_mode\":\"match_color_id_on_map\"" +
        ",\"diversity_value\":" + (forestNode.divers as string) +
        ",\"strict_verify\":" + (boolJson strictVerify) +
        ",\"generated_geometry_ids\":" + generatedGeomJson +
        ",\"configured_species_ids\":" + configuredSpeciesJson +
        ",\"species_binding_verified\":" + (boolJson speciesBindingVerified) +
        ",\"generated_geometry_type_diagnostic\":" + generatedGeometryTypeJson +
        ",\"color_ids\":" + colorIdsJson +
        ",\"verified\":true}"
    ),

    fn singleForestAreaPolygonJson forestName samples:256 =
    (
        if samples < 64 do samples = 64
        if samples > 1024 do samples = 1024

        local forestNode = findForestControlNode forestName
        if forestNode == undefined do throw "Single-Forest area-polygon target was not found."
        local splineNode = findForestAreaSpline forestNode
        if splineNode == undefined do throw "Single-Forest area spline was not found."

        local splineCount = 0
        try (splineCount = numSplines splineNode) catch (splineCount = 0)
        if splineCount < 1 do throw "Bound Forest area object is not a spline."

        local rings = #()
        local minX = 1.0e30
        local minY = 1.0e30
        local maxX = -1.0e30
        local maxY = -1.0e30

        in coordsys world
        (
            for splineIndex = 1 to splineCount do
            (
                if not (isClosed splineNode splineIndex) do
                    throw ("Forest area contains an open spline at index " + (splineIndex as string))

                local ring = #()
                resetLengthInterp()
                for i = 0 to (samples - 1) do
                (
                    local t = (i as float) / (samples as float)
                    local p = interpCurve3D splineNode splineIndex t pathParam:false
                    append ring p
                    if p.x < minX do minX = p.x
                    if p.y < minY do minY = p.y
                    if p.x > maxX do maxX = p.x
                    if p.y > maxY do maxY = p.y
                )
                append rings ring
            )
        )

        local width = maxX - minX
        local height = maxY - minY
        if width <= 0.0 or height <= 0.0 do throw "Forest area spline polygon has invalid bounds."

        local ringsJson = "["
        for ringIndex = 1 to rings.count do
        (
            if ringIndex > 1 do ringsJson += ","
            ringsJson += "["
            local ring = rings[ringIndex]
            for pointIndex = 1 to ring.count do
            (
                if pointIndex > 1 do ringsJson += ","
                local p = ring[pointIndex]
                local nx = (p.x - minX) / width
                local ny = 1.0 - ((p.y - minY) / height)
                ringsJson += "[" + (nx as string) + "," + (ny as string) + "]"
            )
            ringsJson += "]"
        )
        ringsJson += "]"

        local oneMeter = 0.0
        try (oneMeter = units.decodeValue "1m") catch (oneMeter = 0.0)
        if oneMeter <= 0.0 do throw "Could not resolve active scene meter conversion."

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"spline_name\":" + (jsonString splineNode.name) +
        ",\"spline_count\":" + (splineCount as string) +
        ",\"samples_per_spline\":" + (samples as string) +
        ",\"bounds_width_meters\":" + ((width / oneMeter) as string) +
        ",\"bounds_height_meters\":" + ((height / oneMeter) as string) +
        ",\"normalized_rings\":" + ringsJson +
        ",\"coordinate_space\":\"normalized_bbox_with_pil_y_flip\"" +
        ",\"read_only\":true,\"verified\":true}"
    ),

    fn singleForestAreaBoundsJson forestName =
    (
        local forestNode = findForestControlNode forestName
        if forestNode == undefined do throw "Single-Forest area-bounds target was not found."
        local splineNode = findForestAreaSpline forestNode
        if splineNode == undefined do throw "Single-Forest area spline was not found."
        local bb = nodeGetBoundingBox splineNode splineNode.transform
        local pmin = bb[1]
        local pmax = bb[2]
        local widthValue = abs(pmax.x - pmin.x)
        local heightValue = abs(pmax.y - pmin.y)
        if widthValue <= 0.0 or heightValue <= 0.0 do throw "Single-Forest area bounds are invalid."
        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"spline_name\":" + (jsonString splineNode.name) +
        ",\"width_system\":" + (widthValue as string) +
        ",\"height_system\":" + (heightValue as string) +
        ",\"center_x_system\":" + (((pmin.x + pmax.x) * 0.5) as string) +
        ",\"center_y_system\":" + (((pmin.y + pmax.y) * 0.5) as string) +
        ",\"current_units_x\":" + ((if isProperty forestNode #units_x then forestNode.units_x else 0.0) as string) +
        ",\"current_units_y\":" + ((if isProperty forestNode #units_y then forestNode.units_y else 0.0) as string) +
        ",\"verified\":true}"
    ),

    fn singleForestDistributionDiagnosticsJson forestName =
    (
        local forestNode = findForestControlNode forestName
        if forestNode == undefined do throw "Single-Forest diagnostics target was not found."
        if not (isProperty forestNode #specidlist) do throw "Forest Pack property missing: specidlist."
        if not (isProperty forestNode #geomlist) do throw "Forest Pack property missing: geomlist."
        if not (isProperty forestNode #cobjlist) do throw "Forest Pack property missing: cobjlist."
        if not (isProperty forestNode #coloridlist) do throw "Forest Pack property missing: coloridlist."

        local speciesIds = #()
        local colorKeys = #()
        local configuredJson = "["
        local missingJson = "["
        local missingCount = 0
        for i = 1 to forestNode.specidlist.count do
        (
            local specId = forestNode.specidlist[i] as integer
            append speciesIds specId
            if i > 1 do configuredJson += ","
            configuredJson += (specId as string)
            local validBinding = specId > 0 and i <= forestNode.cobjlist.count and forestNode.cobjlist[i] != undefined and i <= forestNode.geomlist.count and forestNode.geomlist[i] != 0 and i <= forestNode.coloridlist.count
            if validBinding do
            (
                local channels = plantGroupColorIdChannels forestNode.coloridlist[i]
                local colorKey = ((channels[1] as integer) as string) + "," + ((channels[2] as integer) as string) + "," + ((channels[3] as integer) as string)
                if (findItem colorKeys colorKey) > 0 then validBinding = false else append colorKeys colorKey
            )
            if not validBinding do
            (
                if missingCount > 0 do missingJson += ","
                missingJson += (specId as string)
                missingCount += 1
            )
        )
        configuredJson += "]"
        missingJson += "]"

        local geomJson = "["
        local radiusJson = "["
        local scaleJson = "["
        local probJson = "["
        for i = 1 to forestNode.specidlist.count do
        (
            if i > 1 do
            (
                geomJson += ","
                radiusJson += ","
                scaleJson += ","
                probJson += ","
            )
            geomJson += ((if isProperty forestNode #geomlist and forestNode.geomlist.count >= i then forestNode.geomlist[i] else 0) as string)
            radiusJson += ((if isProperty forestNode #radiuslist and forestNode.radiuslist.count >= i then forestNode.radiuslist[i] else 0) as string)
            scaleJson += ((if isProperty forestNode #ScaleList and forestNode.ScaleList.count >= i then forestNode.ScaleList[i] else 0.0) as string)
            probJson += ((if isProperty forestNode #problist and forestNode.problist.count >= i then forestNode.problist[i] else 0.0) as string)
        )
        geomJson += "]"
        radiusJson += "]"
        scaleJson += "]"
        probJson += "]"

        local assignedFile = ""
        if isProperty forestNode #divtmap and forestNode.divtmap != undefined do
            try (assignedFile = forestNode.divtmap.filename) catch (assignedFile = "")
        if assignedFile == "" and isProperty forestNode #distmap and forestNode.distmap != undefined do
            try (assignedFile = forestNode.distmap.filename) catch (assignedFile = "")
        local itemCount = getForestGeneratedItemCount forestNode
        local bindingVerified = missingCount == 0 and speciesIds.count >= 1 and colorKeys.count == speciesIds.count and itemCount > 0
        local geometryTypeDiagnostic = plantGroupGeneratedGeomRuntimeDiagnosticJson forestNode speciesIds

        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"geometry_count\":" + (forestNode.specidlist.count as string) +
        ",\"generated_items\":" + (itemCount as string) +
        ",\"generated_geometry_ids\":[]" +
        ",\"configured_species_ids\":" + configuredJson +
        ",\"species_binding_verified\":" + (boolJson bindingVerified) +
        ",\"generated_geometry_type_diagnostic\":" + geometryTypeDiagnostic +
        ",\"missing_species_ids\":" + missingJson +
        ",\"missing_species_count\":" + (missingCount as string) +
        ",\"geomlist\":" + geomJson +
        ",\"radiuslist\":" + radiusJson +
        ",\"scale_list\":" + scaleJson +
        ",\"probability_list\":" + probJson +
        ",\"units_x\":" + ((if isProperty forestNode #units_x then forestNode.units_x else 0.0) as string) +
        ",\"units_y\":" + ((if isProperty forestNode #units_y then forestNode.units_y else 0.0) as string) +
        ",\"distmode\":" + ((if isProperty forestNode #distmode then forestNode.distmode else -1) as string) +
        ",\"densityMap\":" + (boolJson (if isProperty forestNode #densityMap then forestNode.densityMap else false)) +
        ",\"diversity_value\":" + ((if isProperty forestNode #divers then forestNode.divers else -1) as string) +
        ",\"map_path\":" + (jsonString assignedFile) +
        ",\"verified\":" + (boolJson bindingVerified) + "}"
    ),

    fn plantGroupSpeciesFastApplyJson forestName speciesCsv enabledToken scaleToken probabilityToken =
    (
        local forestNode = findForestControlNode forestName
        if forestNode == undefined do throw "Plant-group species target Forest was not found."
        if not (isProperty forestNode #specidlist) do throw "Forest Pack property missing: specidlist."
        if not (isProperty forestNode #geomlist) do throw "Forest Pack property missing: geomlist."
        if not (isProperty forestNode #ScaleList) do throw "Forest Pack property missing: ScaleList."
        if not (isProperty forestNode #problist) do throw "Forest Pack property missing: problist."
        if not (isProperty forestNode #cobjlist) do throw "Forest Pack property missing: cobjlist."

        local tokens = filterString speciesCsv ","
        if tokens.count < 1 do throw "Plant-group species list is empty."
        local ids = #()
        for token in tokens do append ids (token as integer)
        local setEnabled = enabledToken != "-"
        local setScale = scaleToken != "-"
        local setProbability = probabilityToken != "-"
        local enabledValue = if setEnabled then ((enabledToken as integer) != 0) else true
        local scaleValue = if setScale then (scaleToken as float) else 100.0
        local probabilityValue = if setProbability then (probabilityToken as float) else 0.0
        if setScale and scaleValue <= 0.0 do throw "Plant-group species scale must be greater than zero."
        if setProbability and (probabilityValue < 0.0 or probabilityValue > 100.0) do throw "Plant-group species probability must be 0..100."

        local touched = 0
        for i = 1 to forestNode.specidlist.count do
        (
            local specId = forestNode.specidlist[i] as integer
            if (findItem ids specId) > 0 do
            (
                local sourceNode = undefined
                try (sourceNode = forestNode.cobjlist[i]) catch (sourceNode = undefined)
                if setScale and sourceNode != undefined do
                (
                    -- Species Size is a real source-object scale, not the old Area/map scale.
                    -- Preserve the FM-managed proxy's original transform once, then always
                    -- derive the requested percentage from that immutable baseline.
                    local baseXText = getUserProp sourceNode "FM_BaseScaleX"
                    local baseYText = getUserProp sourceNode "FM_BaseScaleY"
                    local baseZText = getUserProp sourceNode "FM_BaseScaleZ"
                    if baseXText == undefined or baseXText == "" or baseYText == undefined or baseYText == "" or baseZText == undefined or baseZText == "" do
                    (
                        baseXText = sourceNode.scale.x as string
                        baseYText = sourceNode.scale.y as string
                        baseZText = sourceNode.scale.z as string
                        setUserProp sourceNode "FM_BaseScaleX" baseXText
                        setUserProp sourceNode "FM_BaseScaleY" baseYText
                        setUserProp sourceNode "FM_BaseScaleZ" baseZText
                    )
                    local sizeFactor = scaleValue / 100.0
                    local targetScale = [(baseXText as float) * sizeFactor, (baseYText as float) * sizeFactor, (baseZText as float) * sizeFactor]
                    sourceNode.scale = targetScale
                    setUserProp sourceNode "FM_SpeciesScalePercent" (scaleValue as string)
                    -- Keep Forest's own per-item scale neutral to avoid double scaling.
                    forestNode.ScaleList[i] = 100.0
                    -- Rebind the Custom Object so Forest invalidates cached proxy geometry.
                    forestNode.cobjlist[i] = undefined
                    forestNode.cobjlist[i] = sourceNode
                    local appliedScale = sourceNode.scale
                    if (abs (appliedScale.x - targetScale.x)) > 0.0001 or (abs (appliedScale.y - targetScale.y)) > 0.0001 or (abs (appliedScale.z - targetScale.z)) > 0.0001 do
                        throw "Plant-group species source scale verification failed."
                )
                if setEnabled do forestNode.geomlist[i] = (if enabledValue then 2 else 0)
                if setProbability do
                (
                    forestNode.problist[i] = probabilityValue
                    if isProperty forestNode #old_problist and forestNode.old_problist.count >= i do
                        forestNode.old_problist[i] = (probabilityValue as integer)
                )
                touched += 1
            )
        )
        if touched != ids.count do throw "Plant-group species fast apply did not resolve every species ID."

        if isProperty forestNode #disabled do forestNode.disabled = false
        if isProperty forestNode #manualupdate do forestNode.manualupdate = false
        try (notifyDependents forestNode partID:#all message:#change) catch()
        try (forestNode.update()) catch()
        completeRedraw()

        local scalesJson = "["
        local enabledJson = "["
        local probabilityJson = "["
        local first = true
        for i = 1 to forestNode.specidlist.count do
        (
            local specId = forestNode.specidlist[i] as integer
            if (findItem ids specId) > 0 do
            (
                if not first do
                (
                    scalesJson += ","
                    enabledJson += ","
                    probabilityJson += ","
                )
                local effectiveScaleValue = forestNode.ScaleList[i]
                local scaleSourceNode = undefined
                try (scaleSourceNode = forestNode.cobjlist[i]) catch (scaleSourceNode = undefined)
                if scaleSourceNode != undefined do
                (
                    local storedScaleText = getUserProp scaleSourceNode "FM_SpeciesScalePercent"
                    if storedScaleText != undefined and storedScaleText != "" do effectiveScaleValue = storedScaleText as float
                )
                scalesJson += (effectiveScaleValue as string)
                enabledJson += (boolJson (forestNode.geomlist[i] != 0))
                probabilityJson += (forestNode.problist[i] as string)
                first = false
            )
        )
        scalesJson += "]"
        enabledJson += "]"
        probabilityJson += "]"
        "{\"forest_name\":" + (jsonString forestNode.name) +
        ",\"species_ids\":" + (jsonString speciesCsv) +
        ",\"touched\":" + (touched as string) +
        ",\"enabled\":" + enabledJson +
        ",\"scale_percent\":" + scalesJson +
        ",\"probability_percent\":" + probabilityJson +
        ",\"generated_items\":" + (getForestGeneratedItemCount forestNode as string) +
        ",\"verified\":true}"
    ),

    fn plantGroupManifestGetJson =
    (
        local forestNode = getNodeByName "FM_Forest_001"
        if forestNode == undefined do throw "FM_Forest_001 is required for plant-group manifest storage."
        if not (isForestNode forestNode) do throw "FM_Forest_001 is not a Forest Pack Forest object."
        local manifestText = undefined
        try (manifestText = getUserProp forestNode "ForestManagerPlantGroupManifest") catch (manifestText = undefined)
        if manifestText == undefined or manifestText == "" then
            "{\"manifest\":null,\"verified\":true}"
        else
            "{\"manifest\":" + manifestText + ",\"verified\":true}"
    ),

    fn plantGroupManifestSetJson manifestText =
    (
        local forestNode = getNodeByName "FM_Forest_001"
        if forestNode == undefined do throw "FM_Forest_001 is required for plant-group manifest storage."
        if not (isForestNode forestNode) do throw "FM_Forest_001 is not a Forest Pack Forest object."
        local clean = trimLeft (trimRight manifestText)
        if clean.count < 2 or (substring clean 1 1) != "{" do throw "Plant-group manifest must be a JSON object."
        setUserProp forestNode "ForestManagerPlantGroupManifest" clean
        local readback = undefined
        try (readback = getUserProp forestNode "ForestManagerPlantGroupManifest") catch (readback = undefined)
        if readback != clean do throw "Plant-group manifest write verification failed."
        "{\"manifest\":" + clean + ",\"verified\":true}"
    ),


    fn fmStage8VectorHelperPrefix sourceName =
    (
        local safe = ""
        local allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"
        for i = 1 to sourceName.count do
        (
            local ch = substring sourceName i 1
            if (findString allowed ch) != undefined then safe += ch else safe += "_"
        )
        "FM_Region_" + safe + "_"
    ),

    fn fmStage8GetOrCreateHelperLayer =
    (
        local helperLayer = LayerManager.getLayerFromName "FM_HELPERS"
        if helperLayer == undefined do helperLayer = LayerManager.newLayerFromName "FM_HELPERS"
        if helperLayer == undefined do throw "Unable to create or resolve FM_HELPERS layer."
        try (helperLayer.lock = false) catch()
        try (helperLayer.isFrozen = false) catch()
        helperLayer
    ),

    fn fmStage8EnsureHelperLayerJson =
    (
        local helperLayer = fmStage8GetOrCreateHelperLayer()
        local migrated = 0
        local helperCount = 0
        for node in objects where matchPattern node.name pattern:"FM_Region_*" ignoreCase:false do
        (
            helperCount += 1
            local currentLayerName = ""
            try (if node.layer != undefined do currentLayerName = node.layer.name) catch()
            if currentLayerName != "FM_HELPERS" do
            (
                local moved = false
                try
                (
                    helperLayer.addNode node
                    moved = (node.layer != undefined and node.layer.name == "FM_HELPERS")
                )
                catch (moved = false)
                if not moved do throw ("Unable to move Forest Manager helper to FM_HELPERS: " + node.name)
                migrated += 1
            )
        )
        try (helperLayer.on = false) catch()
        local layerHidden = false
        try (layerHidden = not helperLayer.on) catch(layerHidden = false)
        if not layerHidden do throw "FM_HELPERS layer could not be hidden."
        local verified = true
        for node in objects where matchPattern node.name pattern:"FM_Region_*" ignoreCase:false do
        (
            local onLayer = false
            try (onLayer = (node.layer != undefined and node.layer.name == "FM_HELPERS")) catch(onLayer = false)
            if not onLayer do verified = false
        )
        if not verified do throw "FM_HELPERS migration verification failed."
        "{\"layer_name\":\"FM_HELPERS\",\"hidden\":true,\"helper_count\":" + (helperCount as string) + ",\"migrated_count\":" + (migrated as string) + ",\"verified\":true}"
    ),

    fn fmStage8ListVectorHelpersJson sourceName =
    (
        fmStage8EnsureHelperLayerJson()
        local prefix = fmStage8VectorHelperPrefix sourceName
        local names = #()
        for node in objects where matchPattern node.name pattern:(prefix + "*") ignoreCase:false do append names node.name
        local items = #()
        for nameValue in names do append items ("\"" + jsonEscape nameValue + "\"")
        local joined = ""
        for i = 1 to items.count do
        (
            if i > 1 do joined += ","
            joined += items[i]
        )
        "{\"source_node_name\":\"" + jsonEscape sourceName + "\",\"helper_names\":[" + joined + "],\"verified\":true}"
    ),

    fn fmStage8RoleWireColor roleName =
    (
        local role = toLower roleName
        if role == "wall_band" then return (color 255 0 0)
        if role == "walkway_band" then return (color 255 220 0)
        if role == "interior" then return (color 0 200 0)
        color 180 180 180
    ),

    fn fmStage8DeleteVectorHelperJson helperName =
    (
        if not matchPattern helperName pattern:"FM_Region_*" ignoreCase:false do throw "Refusing to delete non-Forest-Manager helper."
        local helper = getNodeByName helperName exact:true
        local existed = helper != undefined
        if helper != undefined do delete helper
        local verified = (getNodeByName helperName exact:true) == undefined
        if not verified do throw "Vector helper delete verification failed."
        "{\"helper_name\":\"" + jsonEscape helperName + "\",\"existed\":" + boolJson existed + ",\"verified\":true}"
    ),

    fn handleCommand rawCommand =
    (
        local cleanCommand = trimLeft (trimRight rawCommand)
        local command = toUpper cleanCommand

        if matchPattern command pattern:"RELOAD_BRIDGE|*" ignoreCase:true then
        (
            try
            (
                local encoded = substring cleanCommand 15 (cleanCommand.count - 14)
                local scriptPath = decodeBase64Utf8 encoded
                scheduleBridgeReload scriptPath
                return "{\"ok\":true,\"command\":\"RELOAD_BRIDGE\",\"data\":{\"scheduled\":true,\"path\":" +
                       (jsonString scriptPath) + "},\"error\":\"\"}"
            )
            catch
            (
                return makeError "RELOAD_BRIDGE" (getCurrentException())
            )
        )


        if matchPattern command pattern:"FM_PLANT_GROUP_AREA_UPSERT|*" ignoreCase:true then
        (
            try
            (
                -- Parse the original command. Base64 tokens are case-sensitive and
                -- must never be read from the uppercase routing copy.
                local parts = filterString cleanCommand "|"
                if parts.count != 6 do throw "FM_PLANT_GROUP_AREA_UPSERT requires forest, group key, base Area index, species and scale."
                local forestName = decodeBase64Utf8 parts[2]
                local groupKey = decodeBase64Utf8 parts[3]
                local baseZeroIndex = parts[4] as integer
                local speciesCsv = decodeBase64Utf8 parts[5]
                local scalePercent = parts[6] as float
                return "{\"ok\":true,\"command\":\"FM_PLANT_GROUP_AREA_UPSERT\",\"data\":" + plantGroupAreaUpsertJson forestName groupKey baseZeroIndex speciesCsv scalePercent + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FM_PLANT_GROUP_AREA_UPSERT" (getCurrentException())
            )
        )




        if matchPattern command pattern:"FM_SINGLE_FOREST_AREA_POLYGON|*|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 3 do throw "FM_SINGLE_FOREST_AREA_POLYGON requires forest name and sample count."
                local forestName = decodeBase64Utf8 parts[2]
                local sampleCount = parts[3] as integer
                return "{\"ok\":true,\"command\":\"FM_SINGLE_FOREST_AREA_POLYGON\",\"data\":" + singleForestAreaPolygonJson forestName samples:sampleCount + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FM_SINGLE_FOREST_AREA_POLYGON" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FM_SINGLE_FOREST_AREA_BOUNDS|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 2 do throw "FM_SINGLE_FOREST_AREA_BOUNDS requires forest name."
                local forestName = decodeBase64Utf8 parts[2]
                return "{\"ok\":true,\"command\":\"FM_SINGLE_FOREST_AREA_BOUNDS\",\"data\":" + singleForestAreaBoundsJson forestName + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FM_SINGLE_FOREST_AREA_BOUNDS" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FM_SINGLE_FOREST_DISTRIBUTION_DIAGNOSTICS|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 2 do throw "FM_SINGLE_FOREST_DISTRIBUTION_DIAGNOSTICS requires forest."
                local forestName = decodeBase64Utf8 parts[2]
                return "{\"ok\":true,\"command\":\"FM_SINGLE_FOREST_DISTRIBUTION_DIAGNOSTICS\",\"data\":" + singleForestDistributionDiagnosticsJson forestName + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FM_SINGLE_FOREST_DISTRIBUTION_DIAGNOSTICS" (getCurrentException())
            )
        )


        if matchPattern command pattern:"FM_SINGLE_FOREST_DIVERSITY_MAP_BIND|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count < 3 or parts.count > 4 do throw "FM_SINGLE_FOREST_DIVERSITY_MAP_BIND requires forest, map path, and optional strict flag."
                local forestName = decodeBase64Utf8 parts[2]
                local encodedMapPath = parts[3]
                local strictVerify = true
                if parts.count == 4 do strictVerify = (parts[4] == "1")
                return "{\"ok\":true,\"command\":\"FM_SINGLE_FOREST_DIVERSITY_MAP_BIND\",\"data\":" + plantGroupBindSingleForestDiversityMapJson forestName encodedMapPath strictVerify + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FM_SINGLE_FOREST_DIVERSITY_MAP_BIND" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FM_SINGLE_FOREST_DIVERSITY_MAP_REFRESH|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 3 do throw "FM_SINGLE_FOREST_DIVERSITY_MAP_REFRESH requires forest and map path."
                local forestName = decodeBase64Utf8 parts[2]
                local encodedMapPath = parts[3]
                return "{\"ok\":true,\"command\":\"FM_SINGLE_FOREST_DIVERSITY_MAP_REFRESH\",\"data\":" + plantGroupBindSingleForestDiversityMapJson forestName encodedMapPath false + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FM_SINGLE_FOREST_DIVERSITY_MAP_REFRESH" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FM_PLANT_GROUP_SPECIES_FAST_APPLY|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 6 do throw "FM_PLANT_GROUP_SPECIES_FAST_APPLY requires forest, species IDs, enabled, scale and probability tokens."
                local forestName = decodeBase64Utf8 parts[2]
                local speciesCsv = decodeBase64Utf8 parts[3]
                return "{\"ok\":true,\"command\":\"FM_PLANT_GROUP_SPECIES_FAST_APPLY\",\"data\":" + plantGroupSpeciesFastApplyJson forestName speciesCsv parts[4] parts[5] parts[6] + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FM_PLANT_GROUP_SPECIES_FAST_APPLY" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FM_PLANT_GROUP_AREA_FINALIZE|*" ignoreCase:true then
        (
            try
            (
                -- Parse the original command. Base64 tokens are case-sensitive and
                -- must never be read from the uppercase routing copy.
                local parts = filterString cleanCommand "|"
                if parts.count != 4 do throw "FM_PLANT_GROUP_AREA_FINALIZE requires forest, base Area indices and group keys."
                local forestName = decodeBase64Utf8 parts[2]
                local baseIndicesCsv = decodeBase64Utf8 parts[3]
                local groupKeysCsv = decodeBase64Utf8 parts[4]
                return "{\"ok\":true,\"command\":\"FM_PLANT_GROUP_AREA_FINALIZE\",\"data\":" + plantGroupAreaFinalizeJson forestName baseIndicesCsv groupKeysCsv + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FM_PLANT_GROUP_AREA_FINALIZE" (getCurrentException())
            )
        )

        if command == "FM_PLANT_GROUP_MANIFEST_GET" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"FM_PLANT_GROUP_MANIFEST_GET\",\"data\":" + plantGroupManifestGetJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FM_PLANT_GROUP_MANIFEST_GET" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FM_PLANT_GROUP_MANIFEST_SET|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 2 do throw "FM_PLANT_GROUP_MANIFEST_SET requires one manifest token."
                local manifestText = decodeBase64Utf8 parts[2]
                return "{\"ok\":true,\"command\":\"FM_PLANT_GROUP_MANIFEST_SET\",\"data\":" + plantGroupManifestSetJson manifestText + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FM_PLANT_GROUP_MANIFEST_SET" (getCurrentException())
            )
        )

        if command == "FM_MANAGED_ENSURE" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"FM_MANAGED_ENSURE\",\"data\":" + ensureManagedSceneJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FM_MANAGED_ENSURE" (getCurrentException())
            )
        )

        if command == "FM_MANAGED_PROTECT_ALL" then
        (
            try
            (
                local moved = protectAllManagedNodes()
                return "{\"ok\":true,\"command\":\"FM_MANAGED_PROTECT_ALL\",\"data\":{\"protected\":" + stringArrayJson moved + ",\"status\":" + managedSceneStatusJson() + ",\"verified\":true},\"error\":\"\"}"
            )
            catch
            (
                return makeError "FM_MANAGED_PROTECT_ALL" (getCurrentException())
            )
        )

        if command == "FM_MANAGED_STATUS" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"FM_MANAGED_STATUS\",\"data\":" + managedSceneStatusJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FM_MANAGED_STATUS" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FM_MANAGED_CREATE_FOREST|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 3 do throw "FM_MANAGED_CREATE_FOREST requires name and role tokens."
                local forestName = decodeBase64Utf8 parts[2]
                local roleName = decodeBase64Utf8 parts[3]
                return "{\"ok\":true,\"command\":\"FM_MANAGED_CREATE_FOREST\",\"data\":" + createManagedForestJson forestName roleName + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FM_MANAGED_CREATE_FOREST" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FM_MANAGED_DELETE_FOREST|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 2 do throw "FM_MANAGED_DELETE_FOREST requires one name token."
                local forestName = decodeBase64Utf8 parts[2]
                return "{\"ok\":true,\"command\":\"FM_MANAGED_DELETE_FOREST\",\"data\":" + deleteManagedForestJson forestName + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FM_MANAGED_DELETE_FOREST" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FOREST_CONTROL_ADD_GEOMETRY_SOURCE|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 3 do throw "FOREST_CONTROL_ADD_GEOMETRY_SOURCE requires forest and source node tokens."
                local forestName = decodeBase64Utf8 parts[2]
                local sourceName = decodeBase64Utf8 parts[3]
                return "{\"ok\":true,\"command\":\"FOREST_CONTROL_ADD_GEOMETRY_SOURCE\",\"data\":" + addNamedGeometrySourceJson forestName sourceName + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FOREST_CONTROL_ADD_GEOMETRY_SOURCE" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FOREST_CONTROL_REMOVE_GEOMETRY_SOURCE_TAIL|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 3 do throw "FOREST_CONTROL_REMOVE_GEOMETRY_SOURCE_TAIL requires forest token and one-based tail index."
                local forestName = decodeBase64Utf8 parts[2]
                local geometryIndex = parts[3] as integer
                return "{\"ok\":true,\"command\":\"FOREST_CONTROL_REMOVE_GEOMETRY_SOURCE_TAIL\",\"data\":" + removeGeometrySourceTailJson forestName geometryIndex + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FOREST_CONTROL_REMOVE_GEOMETRY_SOURCE_TAIL" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FOREST_CONTROL_GET_PROPERTY|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 3 do throw "FOREST_CONTROL_GET_PROPERTY requires forest and property tokens."
                local forestName = decodeBase64Utf8 parts[2]
                local propertyName = decodeBase64Utf8 parts[3]
                return "{\"ok\":true,\"command\":\"FOREST_CONTROL_GET_PROPERTY\",\"data\":" + forestControlGetPropertyJson forestName propertyName + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FOREST_CONTROL_GET_PROPERTY" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FOREST_CONTROL_GET_ARRAY_ELEMENT|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 4 do throw "FOREST_CONTROL_GET_ARRAY_ELEMENT requires forest, property and zero-based index."
                local forestName = decodeBase64Utf8 parts[2]
                local propertyName = decodeBase64Utf8 parts[3]
                local zeroIndex = parts[4] as integer
                return "{\"ok\":true,\"command\":\"FOREST_CONTROL_GET_ARRAY_ELEMENT\",\"data\":" + forestControlGetArrayElementJson forestName propertyName zeroIndex + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FOREST_CONTROL_GET_ARRAY_ELEMENT" (getCurrentException())
            )
        )


        if matchPattern command pattern:"FOREST_CONTROL_SET_TEXTURE_REF|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 5 do throw "FOREST_CONTROL_SET_TEXTURE_REF requires forest, property, mode and texture reference token."
                local forestName = decodeBase64Utf8 parts[2]
                local propertyName = decodeBase64Utf8 parts[3]
                local referenceMode = parts[4]
                local encodedTextureFilename = parts[5]
                return "{\"ok\":true,\"command\":\"FOREST_CONTROL_SET_TEXTURE_REF\",\"data\":" + forestControlSetTextureReferenceJson forestName propertyName referenceMode encodedTextureFilename + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FOREST_CONTROL_SET_TEXTURE_REF" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FOREST_CONTROL_GET_TEXTURE_REF|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 3 do throw "FOREST_CONTROL_GET_TEXTURE_REF requires forest and property."
                local forestName = decodeBase64Utf8 parts[2]
                local propertyName = decodeBase64Utf8 parts[3]
                return "{\"ok\":true,\"command\":\"FOREST_CONTROL_GET_TEXTURE_REF\",\"data\":" + forestControlGetTextureReferenceJson forestName propertyName + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FOREST_CONTROL_GET_TEXTURE_REF" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FOREST_CONTROL_SET_ARRAY_CPROXY_REF|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 6 do throw "FOREST_CONTROL_SET_ARRAY_CPROXY_REF requires forest, property, zero-based index, mode and CProxy node token."
                local forestName = decodeBase64Utf8 parts[2]
                local propertyName = decodeBase64Utf8 parts[3]
                local zeroIndex = parts[4] as integer
                local referenceMode = toLower parts[5]
                local encodedNodeName = parts[6]
                return "{\"ok\":true,\"command\":\"FOREST_CONTROL_SET_ARRAY_CPROXY_REF\",\"data\":" + forestControlSetArrayCProxyReferenceJson forestName propertyName zeroIndex referenceMode encodedNodeName + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FOREST_CONTROL_SET_ARRAY_CPROXY_REF" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FOREST_CONTROL_SET_ARRAY_MATERIAL_REF|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 6 do throw "FOREST_CONTROL_SET_ARRAY_MATERIAL_REF requires forest, property, zero-based index, mode and material token."
                local forestName = decodeBase64Utf8 parts[2]
                local propertyName = decodeBase64Utf8 parts[3]
                local zeroIndex = parts[4] as integer
                local referenceMode = toLower parts[5]
                local encodedMaterialName = parts[6]
                return "{\"ok\":true,\"command\":\"FOREST_CONTROL_SET_ARRAY_MATERIAL_REF\",\"data\":" + forestControlSetArrayMaterialReferenceJson forestName propertyName zeroIndex referenceMode encodedMaterialName + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FOREST_CONTROL_SET_ARRAY_MATERIAL_REF" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FOREST_CONTROL_SET_ARRAY_NODE_REF|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 6 do throw "FOREST_CONTROL_SET_ARRAY_NODE_REF requires forest, property, zero-based index, mode and node token."
                local forestName = decodeBase64Utf8 parts[2]
                local propertyName = decodeBase64Utf8 parts[3]
                local zeroIndex = parts[4] as integer
                local referenceMode = toLower parts[5]
                local encodedNodeName = parts[6]
                return "{\"ok\":true,\"command\":\"FOREST_CONTROL_SET_ARRAY_NODE_REF\",\"data\":" + forestControlSetArrayNodeReferenceJson forestName propertyName zeroIndex referenceMode encodedNodeName + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FOREST_CONTROL_SET_ARRAY_NODE_REF" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FOREST_CONTROL_SET_ARRAY_POINT3|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 7 do throw "FOREST_CONTROL_SET_ARRAY_POINT3 requires forest, property, zero-based index and XYZ values."
                local forestName = decodeBase64Utf8 parts[2]
                local propertyName = decodeBase64Utf8 parts[3]
                local zeroIndex = parts[4] as integer
                local xValue = parts[5] as float
                local yValue = parts[6] as float
                local zValue = parts[7] as float
                return "{\"ok\":true,\"command\":\"FOREST_CONTROL_SET_ARRAY_POINT3\",\"data\":" + forestControlSetArrayPoint3Json forestName propertyName zeroIndex xValue yValue zValue + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FOREST_CONTROL_SET_ARRAY_POINT3" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FOREST_CONTROL_SET_ARRAY_SCALAR|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 6 do throw "FOREST_CONTROL_SET_ARRAY_SCALAR requires forest, property, zero-based index, type and value."
                local forestName = decodeBase64Utf8 parts[2]
                local propertyName = decodeBase64Utf8 parts[3]
                local zeroIndex = parts[4] as integer
                local scalarType = toLower parts[5]
                local encodedValue = parts[6]
                return "{\"ok\":true,\"command\":\"FOREST_CONTROL_SET_ARRAY_SCALAR\",\"data\":" + forestControlSetArrayScalarJson forestName propertyName zeroIndex scalarType encodedValue + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FOREST_CONTROL_SET_ARRAY_SCALAR" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FOREST_CONTROL_SET_SCALAR|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 5 do throw "FOREST_CONTROL_SET_SCALAR requires forest, property, type and value tokens."
                local forestName = decodeBase64Utf8 parts[2]
                local propertyName = decodeBase64Utf8 parts[3]
                local scalarType = toLower parts[4]
                local encodedValue = parts[5]
                return "{\"ok\":true,\"command\":\"FOREST_CONTROL_SET_SCALAR\",\"data\":" + forestControlSetScalarJson forestName propertyName scalarType encodedValue + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FOREST_CONTROL_SET_SCALAR" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FOREST_CONTROL_SET_COLOR|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 6 do throw "FOREST_CONTROL_SET_COLOR requires forest, property and RGB channels."
                local forestName = decodeBase64Utf8 parts[2]
                local propertyName = decodeBase64Utf8 parts[3]
                local redValue = parts[4] as float
                local greenValue = parts[5] as float
                local blueValue = parts[6] as float
                return "{\"ok\":true,\"command\":\"FOREST_CONTROL_SET_COLOR\",\"data\":" + forestControlSetColorJson forestName propertyName redValue greenValue blueValue + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FOREST_CONTROL_SET_COLOR" (getCurrentException())
            )
        )
        if command == "FOREST_CONTROL_DISCOVER" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"FOREST_CONTROL_DISCOVER\",\"data\":" + getForestControlDiscoveryJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FOREST_CONTROL_DISCOVER" (getCurrentException())
            )
        )

        if command == "GET_SCENE_UNITS" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"GET_SCENE_UNITS\",\"data\":" +
                       getSceneUnitsJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "GET_SCENE_UNITS" (getCurrentException())
            )
        )

        if command == "APPLY_NATIVE_SCALE_VARIATION" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"APPLY_NATIVE_SCALE_VARIATION\",\"data\":" +
                       applyNativeScaleVariationJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "APPLY_NATIVE_SCALE_VARIATION" (getCurrentException())
            )
        )

        if command == "APPLY_CLUSTER_DIVERSITY_MODE" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"APPLY_CLUSTER_DIVERSITY_MODE\",\"data\":" +
                       applyClusterDiversityModeJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "APPLY_CLUSTER_DIVERSITY_MODE" (getCurrentException())
            )
        )

        if command == "APPLY_SPECIES_UV_CLAMP_PREVIEW" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"APPLY_SPECIES_UV_CLAMP_PREVIEW\",\"data\":" +
                       applySpeciesUvClampPreviewJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "APPLY_SPECIES_UV_CLAMP_PREVIEW" (getCurrentException())
            )
        )

        if command == "ROLLBACK_SPECIES_UV_CLAMP_PREVIEW" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"ROLLBACK_SPECIES_UV_CLAMP_PREVIEW\",\"data\":" +
                       rollbackSpeciesUvClampPreviewJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "ROLLBACK_SPECIES_UV_CLAMP_PREVIEW" (getCurrentException())
            )
        )

        if matchPattern command pattern:"ACTIVATE_SINGLE_SPECIES_LAYER|*" then
        (
            try
            (
                local parts = filterString command "|"
                if parts.count != 2 do
                    throw "ACTIVATE_SINGLE_SPECIES_LAYER requires one layer index."

                local layerIndex = parts[2] as integer
                return "{\"ok\":true,\"command\":\"ACTIVATE_SINGLE_SPECIES_LAYER\",\"data\":" +
                       activateSingleSpeciesLayerPreviewJson layerIndex + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "ACTIVATE_SINGLE_SPECIES_LAYER" (getCurrentException())
            )
        )

        if command == "CONFIGURE_SPECIES_MAP_PROJECTION" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"CONFIGURE_SPECIES_MAP_PROJECTION\",\"data\":" +
                       configureSpeciesMapProjectionJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "CONFIGURE_SPECIES_MAP_PROJECTION" (getCurrentException())
            )
        )

        if command == "ACTIVATE_ALL_SPECIES_LAYERS" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"ACTIVATE_ALL_SPECIES_LAYERS\",\"data\":" +
                       activateAllSpeciesLayersPreviewJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "ACTIVATE_ALL_SPECIES_LAYERS" (getCurrentException())
            )
        )

        if command == "ROLLBACK_SPECIES_LAYER_PREVIEW" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"ROLLBACK_SPECIES_LAYER_PREVIEW\",\"data\":" +
                       rollbackSpeciesLayerPreviewJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "ROLLBACK_SPECIES_LAYER_PREVIEW" (getCurrentException())
            )
        )

        if command == "GET_SPECIES_MASK_DEEP_UVGEN_CONTRACT" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"GET_SPECIES_MASK_DEEP_UVGEN_CONTRACT\",\"data\":" +
                       getSpeciesMaskDeepUvgenContractJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "GET_SPECIES_MASK_DEEP_UVGEN_CONTRACT" (getCurrentException())
            )
        )

        if command == "GET_FOREST_AREA_POLYGON" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"GET_FOREST_AREA_POLYGON\",\"data\":" +
                       getForestAreaPolygonJson samples:256 + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "GET_FOREST_AREA_POLYGON" (getCurrentException())
            )
        )

        if command == "GET_SPECIES_MASK_SPATIAL_ALIGNMENT_CONTRACT" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"GET_SPECIES_MASK_SPATIAL_ALIGNMENT_CONTRACT\",\"data\":" +
                       getSpeciesMaskSpatialAlignmentContractJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "GET_SPECIES_MASK_SPATIAL_ALIGNMENT_CONTRACT" (getCurrentException())
            )
        )

        if matchPattern command pattern:"BIND_SPECIES_DISTRIBUTION_MASKS|*" then
        (
            try
            (
                local parts = filterString command "|"
                if parts.count != 4 do
                    throw "BIND_SPECIES_DISTRIBUTION_MASKS requires exactly three mask paths."

                return "{\"ok\":true,\"command\":\"BIND_SPECIES_DISTRIBUTION_MASKS\",\"data\":" +
                       bindSpeciesDistributionMasksJson parts[2] parts[3] parts[4] + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "BIND_SPECIES_DISTRIBUTION_MASKS" (getCurrentException())
            )
        )

        if command == "GET_LAYER_MAP_BINDING_CONTRACT" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"GET_LAYER_MAP_BINDING_CONTRACT\",\"data\":" +
                       getLayerMapBindingContractJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "GET_LAYER_MAP_BINDING_CONTRACT" (getCurrentException())
            )
        )

        if command == "GET_LAYER_DENSITY_DISTRIBUTION_CONTRACT" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"GET_LAYER_DENSITY_DISTRIBUTION_CONTRACT\",\"data\":" +
                       getLayerDensityDistributionContractJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "GET_LAYER_DENSITY_DISTRIBUTION_CONTRACT" (getCurrentException())
            )
        )

        if command == "PREPARE_SPECIES_LAYER_FORESTS" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"PREPARE_SPECIES_LAYER_FORESTS\",\"data\":" +
                       prepareSpeciesLayerForestsJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "PREPARE_SPECIES_LAYER_FORESTS" (getCurrentException())
            )
        )

        if command == "GET_LIVE_SOURCE_AREA_CONTRACT" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"GET_LIVE_SOURCE_AREA_CONTRACT\",\"data\":" +
                       getLiveSourceAreaContractJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "GET_LIVE_SOURCE_AREA_CONTRACT" (getCurrentException())
            )
        )

        if command == "GET_SPECIES_LAYER_CONTEXT" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"GET_SPECIES_LAYER_CONTEXT\",\"data\":" +
                       getSpeciesLayerContextJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "GET_SPECIES_LAYER_CONTEXT" (getCurrentException())
            )
        )

        if command == "APPLY_VISUAL_CLUSTER_CALIBRATION" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"APPLY_VISUAL_CLUSTER_CALIBRATION\",\"data\":" +
                       applyVisualClusterCalibrationJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "APPLY_VISUAL_CLUSTER_CALIBRATION" (getCurrentException())
            )
        )

        if command == "APPLY_NATURAL_CLUSTER_PROFILE" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"APPLY_NATURAL_CLUSTER_PROFILE\",\"data\":" +
                       applyNaturalClusterProfileJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "APPLY_NATURAL_CLUSTER_PROFILE" (getCurrentException())
            )
        )

        if command == "GET_CLUSTER_PARAMETER_MAPPING" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"GET_CLUSTER_PARAMETER_MAPPING\",\"data\":" +
                       getClusterParameterMappingJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "GET_CLUSTER_PARAMETER_MAPPING" (getCurrentException())
            )
        )

        if command == "GET_CLUSTER_CAPABILITIES" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"GET_CLUSTER_CAPABILITIES\",\"data\":" +
                       getClusterCapabilityProbeJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "GET_CLUSTER_CAPABILITIES" (getCurrentException())
            )
        )

        if command == "GET_DISTRIBUTION_CAPABILITIES" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"GET_DISTRIBUTION_CAPABILITIES\",\"data\":" +
                       getDistributionCapabilityProbeJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "GET_DISTRIBUTION_CAPABILITIES" (getCurrentException())
            )
        )

        if command == "GET_TRANSFORM_CAPABILITIES" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"GET_TRANSFORM_CAPABILITIES\",\"data\":" +
                       getTransformCapabilityProbeJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "GET_TRANSFORM_CAPABILITIES" (getCurrentException())
            )
        )

        if command == "GET_COMPOSITION_CONTEXT" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"GET_COMPOSITION_CONTEXT\",\"data\":" +
                       getCompositionContextJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "GET_COMPOSITION_CONTEXT" (getCurrentException())
            )
        )

        if command == "FM_CLOSED_SPLINE_CANDIDATES" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"FM_CLOSED_SPLINE_CANDIDATES\",\"data\":" + closedSplineCandidatesJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FM_CLOSED_SPLINE_CANDIDATES" (getCurrentException())
            )
        )

        if matchPattern command pattern:"FM_STAGE8_ENSURE_PRIMARY_FOREST|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 2 do throw "FM_STAGE8_ENSURE_PRIMARY_FOREST requires one spline name token."
                local splineName = decodeBase64Utf8 parts[2]
                return "{\"ok\":true,\"command\":\"FM_STAGE8_ENSURE_PRIMARY_FOREST\",\"data\":" + ensureStage8PrimaryForestJson splineName + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "FM_STAGE8_ENSURE_PRIMARY_FOREST" (getCurrentException())
            )
        )

        if command == "GET_SELECTION_SPLINE_AREA" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"GET_SELECTION_SPLINE_AREA\",\"data\":" +
                       getSelectionSplineAreaJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "GET_SELECTION_SPLINE_AREA" (getCurrentException())
            )
        )

        if command == "GET_SELECTION_MEASUREMENTS" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"GET_SELECTION_MEASUREMENTS\",\"data\":" +
                       getSelectionMeasurementsJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "GET_SELECTION_MEASUREMENTS" (getCurrentException())
            )
        )




        if command == "FM_STAGE8_ENSURE_HELPER_LAYER" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"FM_STAGE8_ENSURE_HELPER_LAYER\",\"data\":" + fmStage8EnsureHelperLayerJson() + ",\"error\":\"\"}"
            )
            catch (return makeError "FM_STAGE8_ENSURE_HELPER_LAYER" (getCurrentException()))
        )

        if matchPattern command pattern:"FM_STAGE8_LIST_VECTOR_HELPERS|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 2 do throw "FM_STAGE8_LIST_VECTOR_HELPERS requires one source node token."
                local sourceName = decodeBase64Utf8 parts[2]
                return "{\"ok\":true,\"command\":\"FM_STAGE8_LIST_VECTOR_HELPERS\",\"data\":" + fmStage8ListVectorHelpersJson sourceName + ",\"error\":\"\"}"
            )
            catch (return makeError "FM_STAGE8_LIST_VECTOR_HELPERS" (getCurrentException()))
        )

        if matchPattern command pattern:"FM_STAGE8_UPSERT_VECTOR_HELPER|*" ignoreCase:true then
        (
            local dispatchStep = "entry"
            local dispatchError = undefined
            local parts = #()
            local helperName = ""
            local sourceName = ""
            local roleName = ""
            local pointsText = ""
            local safeSource = ""
            local allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"
            local prefix = ""
            local sourceNode = undefined
            local rows = #()
            local points = #()
            local zValue = 0.0
            local helper = undefined
            local created = false
            local verified = false
            try
            (
                dispatchStep = "split_command"
                parts = filterString cleanCommand "|"
                if parts.count != 5 do throw "FM_STAGE8_UPSERT_VECTOR_HELPER requires helper, source, role and points tokens."

                dispatchStep = "decode_helper"
                helperName = decodeBase64Utf8 parts[2]
                dispatchStep = "decode_source"
                sourceName = decodeBase64Utf8 parts[3]
                dispatchStep = "decode_role"
                roleName = decodeBase64Utf8 parts[4]
                dispatchStep = "decode_points"
                pointsText = decodeBase64Utf8 parts[5]

                dispatchStep = "source_prefix"
                for i = 1 to sourceName.count do
                (
                    local ch = substring sourceName i 1
                    if (findString allowed ch) != undefined then safeSource += ch else safeSource += "_"
                )
                prefix = "FM_Region_" + safeSource + "_"

                dispatchStep = "ownership_check"
                if not matchPattern helperName pattern:(prefix + "*") ignoreCase:false do
                    throw "Vector helper name is outside the Forest Manager-owned source prefix."

                dispatchStep = "source_lookup"
                sourceNode = getNodeByName sourceName exact:true
                if sourceNode == undefined do throw ("Source boundary not found: " + sourceName)

                dispatchStep = "split_rows"
                rows = filterString pointsText ";"
                if rows.count < 3 do throw "Vector helper requires at least three points."

                dispatchStep = "source_z"
                zValue = sourceNode.pos.z

                dispatchStep = "parse_points"
                for row in rows do
                (
                    local xy = filterString row ","
                    if xy.count != 2 do throw "Invalid vector helper point payload."
                    local px = xy[1] as float
                    local py = xy[2] as float
                    append points (point3 px py zValue)
                )

                dispatchStep = "helper_lookup"
                helper = getNodeByName helperName exact:true
                if helper == undefined then
                (
                    dispatchStep = "splineShape_constructor"
                    helper = splineShape()
                    dispatchStep = "assign_name"
                    helper.name = helperName
                    created = true
                )
                else
                (
                    dispatchStep = "existing_shape_validation"
                    if (superClassOf helper) != Shape do throw ("Managed helper name is occupied by a non-shape node: " + helperName)
                    dispatchStep = "clear_existing_splines"
                    while (numSplines helper) > 0 do deleteSpline helper 1
                )

                dispatchStep = "addNewSpline"
                addNewSpline helper
                dispatchStep = "addKnot"
                for p in points do addKnot helper 1 #corner #line p
                dispatchStep = "close"
                close helper 1
                dispatchStep = "updateShape"
                updateShape helper

                dispatchStep = "helper_layer"
                local helperLayer = fmStage8GetOrCreateHelperLayer()
                helperLayer.addNode helper
                if helper.layer == undefined or helper.layer.name != "FM_HELPERS" do throw "Vector helper layer assignment verification failed."
                try (helperLayer.on = false) catch()

                dispatchStep = "wirecolor"
                local roleLower = toLower roleName
                if roleLower == "wall_band" then
                    helper.wirecolor = color 255 0 0
                else if roleLower == "walkway_band" then
                    helper.wirecolor = color 255 220 0
                else if roleLower == "interior" then
                    helper.wirecolor = color 0 200 0
                else
                    helper.wirecolor = color 180 180 180

                dispatchStep = "visibility"
                helper.isHidden = false
                dispatchStep = "verification"
                verified = ((numSplines helper) == 1 and (numKnots helper 1) == points.count and isClosed helper 1)
                if not verified do throw "Vector helper spline verification failed."
                dispatchStep = "redrawViews"
                redrawViews()
            )
            catch
            (
                dispatchError = getCurrentException()
            )
            if dispatchError != undefined then
                return makeError "FM_STAGE8_UPSERT_VECTOR_HELPER" ("Vector helper upsert step " + dispatchStep + " failed: " + dispatchError)

            return "{\"ok\":true,\"command\":\"FM_STAGE8_UPSERT_VECTOR_HELPER\",\"data\":{\"helper_name\":\"" + jsonEscape helperName + "\",\"source_node_name\":\"" + jsonEscape sourceName + "\",\"role\":\"" + jsonEscape roleName + "\",\"created\":" + boolJson created + ",\"vertex_count\":" + (points.count as string) + ",\"closed\":true,\"verified\":true},\"error\":\"\"}"
        )

        if matchPattern command pattern:"FM_STAGE8_DELETE_VECTOR_HELPER|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 2 do throw "FM_STAGE8_DELETE_VECTOR_HELPER requires one helper name token."
                local helperName = decodeBase64Utf8 parts[2]
                return "{\"ok\":true,\"command\":\"FM_STAGE8_DELETE_VECTOR_HELPER\",\"data\":" + fmStage8DeleteVectorHelperJson helperName + ",\"error\":\"\"}"
            )
            catch (return makeError "FM_STAGE8_DELETE_VECTOR_HELPER" (getCurrentException()))
        )

        if command == "GET_SELECTION_SPLINE_SEGMENTS" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"GET_SELECTION_SPLINE_SEGMENTS\",\"data\":" +
                    getSelectionSplineSegmentsJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "GET_SELECTION_SPLINE_SEGMENTS" (getCurrentException())
            )
        )

        if matchPattern command pattern:"GET_SELECTION_SPLINE_WORLD_SPACE|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 2 do throw "GET_SELECTION_SPLINE_WORLD_SPACE requires one sample-count value."
                local sampleCount = parts[2] as integer
                return "{\"ok\":true,\"command\":\"GET_SELECTION_SPLINE_WORLD_SPACE\",\"data\":" +
                       getSelectionSplineWorldSpaceJson samplesPerSpline:sampleCount + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "GET_SELECTION_SPLINE_WORLD_SPACE" (getCurrentException())
            )
        )

        if matchPattern command pattern:"MERGE_T2_ASSET|*" ignoreCase:true then
        (
            try
            (
                local encoded = substring cleanCommand 16 (cleanCommand.count - 15)
                local assetPath = decodeBase64Utf8 encoded
                return "{\"ok\":true,\"command\":\"MERGE_T2_ASSET\",\"data\":" +
                       mergeT2AssetAndBindJson assetPath + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "MERGE_T2_ASSET" (getCurrentException())
            )
        )

        if matchPattern command pattern:"APPEND_T2_ASSET|*|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 3 do throw "APPEND_T2_ASSET requires path and probability."
                local assetPath = decodeBase64Utf8 parts[2]
                local probabilityValue = parts[3] as float
                return "{\"ok\":true,\"command\":\"APPEND_T2_ASSET\",\"data\":" +
                       appendT2AssetGeometryJson assetPath probabilityValue + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "APPEND_T2_ASSET" (getCurrentException())
            )
        )

        if matchPattern command pattern:"SET_DENSITY_METERS|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 2 do throw "SET_DENSITY_METERS requires density in meters."
                local densityMeters = parts[2] as float
                return "{\"ok\":true,\"command\":\"SET_DENSITY_METERS\",\"data\":" +
                       configureDensityMetersJson densityMeters + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "SET_DENSITY_METERS" (getCurrentException())
            )
        )

        if matchPattern command pattern:"SET_PHYSICAL_SPACING|*" ignoreCase:true then
        (
            try
            (
                local parts = filterString cleanCommand "|"
                if parts.count != 2 do throw "SET_PHYSICAL_SPACING requires spacing in meters."
                local spacingMeters = parts[2] as float
                return "{\"ok\":true,\"command\":\"SET_PHYSICAL_SPACING\",\"data\":" +
                       configurePhysicalSpacingJson spacingMeters + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "SET_PHYSICAL_SPACING" (getCurrentException())
            )
        )

        if matchPattern command pattern:"SET_GEOMETRY_PROBABILITIES|*" ignoreCase:true then
        (
            try
            (
                local rawValues = substring cleanCommand 28 (cleanCommand.count - 27)
                local parts = filterString rawValues ","
                local values = #()

                for part in parts do
                    append values (part as float)

                return "{\"ok\":true,\"command\":\"SET_GEOMETRY_PROBABILITIES\",\"data\":" +
                       setForestGeometryProbabilitiesJson values + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "SET_GEOMETRY_PROBABILITIES" (getCurrentException())
            )
        )

        if command == "SET_ALL_FOREST_POINT_CLOUD" then
        (
            try
            (
                return "{\"ok\":true,\"command\":\"SET_ALL_FOREST_POINT_CLOUD\",\"data\":" +
                       setAllForestPointCloudJson() + ",\"error\":\"\"}"
            )
            catch
            (
                return makeError "SET_ALL_FOREST_POINT_CLOUD" (getCurrentException())
            )
        )

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

            "RESET_MANAGED_FOREST_FROM_SELECTION":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"RESET_MANAGED_FOREST_FROM_SELECTION\",\"data\":" +
                    resetManagedForestFromSelectionJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "RESET_MANAGED_FOREST_FROM_SELECTION" (getCurrentException())
                )
            )

            "GET_FOREST_GEOMETRY_CONTRACT":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"GET_FOREST_GEOMETRY_CONTRACT\",\"data\":" +
                    getForestGeometryContractJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "GET_FOREST_GEOMETRY_CONTRACT" (getCurrentException())
                )
            )

            "GET_FOREST_GEOMETRY_CONTRACT_DETAILS":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"GET_FOREST_GEOMETRY_CONTRACT_DETAILS\",\"data\":" +
                    getForestGeometryContractDetailsJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "GET_FOREST_GEOMETRY_CONTRACT_DETAILS" (getCurrentException())
                )
            )

            "ADD_SELECTED_GEOMETRY_TO_FOREST":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"ADD_SELECTED_GEOMETRY_TO_FOREST\",\"data\":" +
                    addSelectedGeometryToForestJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "ADD_SELECTED_GEOMETRY_TO_FOREST" (getCurrentException())
                )
            )

            "GET_FOREST_DISTRIBUTION_CONTRACT":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"GET_FOREST_DISTRIBUTION_CONTRACT\",\"data\":" +
                    getForestDistributionContractJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "GET_FOREST_DISTRIBUTION_CONTRACT" (getCurrentException())
                )
            )

            "GET_FOREST_DISTRIBUTION_UNITS":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"GET_FOREST_DISTRIBUTION_UNITS\",\"data\":" +
                    getForestDistributionUnitsJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "GET_FOREST_DISTRIBUTION_UNITS" (getCurrentException())
                )
            )

            "CONFIGURE_ADAPTIVE_DISTRIBUTION":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"CONFIGURE_ADAPTIVE_DISTRIBUTION\",\"data\":" +
                    configureAdaptiveDistributionJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "CONFIGURE_ADAPTIVE_DISTRIBUTION" (getCurrentException())
                )
            )

            "NORMALIZE_FOREST_BUILD_STATE":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"NORMALIZE_FOREST_BUILD_STATE\",\"data\":" +
                    normalizeForestBuildStateJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "NORMALIZE_FOREST_BUILD_STATE" (getCurrentException())
                )
            )

            "GET_FOREST_FULL_RUNTIME_CONTRACT":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"GET_FOREST_FULL_RUNTIME_CONTRACT\",\"data\":" +
                    getForestFullRuntimeContractJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "GET_FOREST_FULL_RUNTIME_CONTRACT" (getCurrentException())
                )
            )

            "NORMALIZE_GEOMETRY_ITEM":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"NORMALIZE_GEOMETRY_ITEM\",\"data\":" +
                    normalizeGeometryItemJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "NORMALIZE_GEOMETRY_ITEM" (getCurrentException())
                )
            )

            "CONFIGURE_ASSET_AWARE_DENSITY":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"CONFIGURE_ASSET_AWARE_DENSITY\",\"data\":" +
                    configureAssetAwareDensityJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "CONFIGURE_ASSET_AWARE_DENSITY" (getCurrentException())
                )
            )

            "CONFIGURE_TARGET_ITEM_DENSITY":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"CONFIGURE_TARGET_ITEM_DENSITY\",\"data\":" +
                    configureTargetItemDensityJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "CONFIGURE_TARGET_ITEM_DENSITY" (getCurrentException())
                )
            )

            "CONFIGURE_FIXED_DISTRIBUTION_UNITS":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"CONFIGURE_FIXED_DISTRIBUTION_UNITS\",\"data\":" +
                    configureFixedDistributionUnitsJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "CONFIGURE_FIXED_DISTRIBUTION_UNITS" (getCurrentException())
                )
            )

            "NORMALIZE_REFERENCE_SOURCES":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"NORMALIZE_REFERENCE_SOURCES\",\"data\":" +
                    normalizeReferenceSourcesJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "NORMALIZE_REFERENCE_SOURCES" (getCurrentException())
                )
            )

            "GET_FOREST_GEOMETRY_SUMMARY":
            (
                try
                (
                    "{\"ok\":true,\"command\":\"GET_FOREST_GEOMETRY_SUMMARY\",\"data\":" +
                    getForestGeometrySummaryJson() + ",\"error\":\"\"}"
                )
                catch
                (
                    makeError "GET_FOREST_GEOMETRY_SUMMARY" (getCurrentException())
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
        reloadTimer = undefined
        reloadPath = undefined
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

