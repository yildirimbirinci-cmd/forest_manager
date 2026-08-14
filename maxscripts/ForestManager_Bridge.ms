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
        ",\"bridge_version\":\"0.5.3\"}"
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
