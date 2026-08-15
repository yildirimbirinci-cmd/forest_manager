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
        ",\"bridge_version\":\"0.9.41\"" +
        ",\"bridge_build_id\":\"stage5d25-density-restartsafe-20260815a\"}"
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
            local p = pathInterp node splineIndex t
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
        local refLayer = LayerManager.getLayerFromName "FM_References"
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
            if nodeLayer != undefined do result = (nodeLayer.name == "FM_References")
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
        local layerName = "FM_References"
        local refLayer = LayerManager.getLayerFromName layerName
        if refLayer == undefined do
            refLayer = LayerManager.newLayerFromName layerName
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

        -- Layer visibility off. Do not hide the Forest object itself.
        try (refLayer.on = false) catch()

        true
    ),

    fn raiseBridgeError message =
    (
        throw message
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
            raiseBridgeError (currentExceptionDetails "MERGE_STEP[mergeMAXFile]: ")
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
            raiseBridgeError ("MERGE_STEP[chooseMergedSourceNode]: " + (getCurrentException()))
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
            raiseBridgeError ("MERGE_STEP[prepareReferenceNode]: " + (getCurrentException()))
        )

        local dimensions = undefined
        try
        (
            dimensions = bindForestGeometrySource forestNode sourceNode
        )
        catch
        (
            raiseBridgeError ("MERGE_STEP[bindForestGeometrySource]: " + (getCurrentException()))
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
            raiseBridgeError (currentExceptionDetails "APPEND_STEP[mergeMAXFile]: ")
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
            raiseBridgeError ("APPEND_STEP[prepareReferenceNode]: " + (getCurrentException()))
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
            raiseBridgeError ("APPEND_STEP[setGeometryItemAtIndex]: " + (getCurrentException()))
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

        if valueClass == "String" then
            return (jsonString value)

        jsonString (value as string)
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
        )

        try
        (
            legacy.disabled = true
            layers[1].disabled = false
            layers[2].disabled = true
            layers[3].disabled = true

            for layerCoord in layerCoords do
            (
                layerCoord.realWorldScale = true
                layerCoord.realWorldWidth = splineWidth
                layerCoord.realWorldHeight = splineHeight
                layerCoord.U_Tile = false
                layerCoord.V_Tile = false

                if layerCoord.realWorldScale != true do throw "Real-world UV scale verification failed."
                if abs(layerCoord.realWorldWidth - splineWidth) > 0.001 do throw "Real-world UV width verification failed."
                if abs(layerCoord.realWorldHeight - splineHeight) > 0.001 do throw "Real-world UV height verification failed."
                if layerCoord.U_Tile != false do throw "U_Tile clamp verification failed."
                if layerCoord.V_Tile != false do throw "V_Tile clamp verification failed."
            )

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
            )
            try (legacy.disabled = oldLegacyDisabled) catch()
            for i = 1 to layers.count do
                try (layers[i].disabled = oldLayerDisabled[i]) catch()
            throw
        )

        "{\"mode\":\"uv_clamp_visual_preview\"" +
        ",\"forest_name\":" + (jsonString target.name) +
        ",\"source_name\":" +
            (if target.cobjlist.count > 0 and target.cobjlist[1] != undefined
                then jsonString target.cobjlist[1].name else "\"\"") +
        ",\"u_tile\":false" +
        ",\"v_tile\":false" +
        ",\"real_world_scale\":true" +
        ",\"real_world_width_meters\":" + ((splineWidth / oneMeter) as string) +
        ",\"real_world_height_meters\":" + ((splineHeight / oneMeter) as string) +
        ",\"spline_name\":" + (jsonString sourceSpline.name) +
        ",\"density_meters_x\":" + ((target.units_x / oneMeter) as string) +
        ",\"density_meters_y\":" + ((target.units_y / oneMeter) as string) +
        ",\"legacy_forest_disabled\":true" +
        ",\"only_foreground_layer_active\":true" +
        ",\"transactional\":true" +
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

        "{\"mode\":\"single_layer_visual_preview\"" +
        ",\"active_layer_index\":" + (layerIndex as string) +
        ",\"legacy_forest\":" + (jsonString legacy.name) +
        ",\"legacy_forest_disabled\":" + (boolJson legacy.disabled) +
        ",\"layers\":" + layersJson +
        ",\"density_units_preserved\":true" +
        ",\"transactional\":true" +
        ",\"verified\":true}"
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

        local refsLayer = LayerManager.getLayerFromName "FM_References"
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
            if reloadTimer != undefined do
            (
                reloadTimer.Stop()
                reloadTimer.Dispose()
            )
        )
        catch()

        reloadPath = scriptPath
        reloadTimer = dotNetObject "System.Windows.Forms.Timer"
        reloadTimer.Interval = 250
        dotNet.addEventHandler reloadTimer "Tick" (fn onForestManagerBridgeReloadTick sender args =
        (
            if ForestManagerBridge != undefined do
            (
                local pathToLoad = ForestManagerBridge.reloadPath
                try
                (
                    if ForestManagerBridge.reloadTimer != undefined do
                    (
                        ForestManagerBridge.reloadTimer.Stop()
                        ForestManagerBridge.reloadTimer.Dispose()
                        ForestManagerBridge.reloadTimer = undefined
                    )

                    if pathToLoad != undefined and doesFileExist pathToLoad then
                    (
                        format "Forest Manager Bridge auto-reload: %\n" pathToLoad
                        fileIn pathToLoad
                    )
                    else
                    (
                        format "Forest Manager Bridge auto-reload failed: script not found.\n"
                    )
                )
                catch
                (
                    format "Forest Manager Bridge auto-reload failed: %\n" (getCurrentException())
                )
            )
        ))
        reloadTimer.Start()
        true
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
            if reloadTimer != undefined do
            (
                reloadTimer.Stop()
                reloadTimer.Dispose()
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
