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
        ",\"bridge_version\":\"0.9.0\"}"
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

        if oldForest != undefined then
        (
            local managedForest = false
            try (managedForest = isKindOf oldForest ::Forest_Pro) catch (managedForest = false)
            if not managedForest do
                throw "FM_Forest_001 exists but is not a Forest Pack object. Refusing to delete it."

            delete oldForest
            oldForestDeleted = true
        )

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
            ",\"geometry_count\":0" +
            ",\"verified\":true}"
        )
        catch
        (
            local message = getCurrentException()
            try (if forestNode != undefined do delete forestNode) catch()
            throw message
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

    fn chooseMergedSourceNode newObjects =
    (
        local sourceNode = undefined

        -- Prefer a top-level group head so grouped vegetation stays intact.
        for obj in newObjects while sourceNode == undefined do
        (
            if obj.parent == undefined then
            (
                local groupHead = false
                try (groupHead = isGroupHead obj) catch (groupHead = false)
                if groupHead do sourceNode = obj
            )
        )

        -- Otherwise prefer a top-level geometry node.
        for obj in newObjects while sourceNode == undefined do
        (
            if obj.parent == undefined then
            (
                try
                (
                    if superClassOf obj == GeometryClass do sourceNode = obj
                )
                catch()
            )
        )

        -- Finally use any top-level object, then the first merged node.
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

        local beforeObjects = objects as array
        local beforeCount = beforeObjects.count

        clearSelection()

        local mergeResult = mergeMAXFile assetPath #select #autoRenameDups #useMergedMtlDups quiet:true

        local afterObjects = objects as array
        local newObjects = for obj in afterObjects where (findItem beforeObjects obj) == 0 collect obj

        if newObjects.count < 1 do
            throw "T2 asset merge produced no new scene nodes."

        local sourceNode = chooseMergedSourceNode newObjects
        if sourceNode == undefined do
            throw "Could not choose a Forest source from merged nodes."

        -- Match T2's existing merge behavior for top-level assets.
        if sourceNode.parent == undefined do
        (
            try (sourceNode.position = [0,0,0]) catch()
        )

        prepareReferenceNode sourceNode

        local dimensions = bindForestGeometrySource forestNode sourceNode

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
        mergeMAXFile assetPath #select #autoRenameDups #useMergedMtlDups quiet:true
        local afterObjects = objects as array
        local newObjects = for obj in afterObjects where (findItem beforeObjects obj) == 0 collect obj
        if newObjects.count < 1 do throw "T2 asset merge produced no new scene nodes."

        local sourceNode = chooseMergedSourceNode newObjects
        if sourceNode == undefined do throw "Could not choose a Forest source from merged nodes."

        if findGeometrySourceIndexByName forestNode sourceNode.name > 0 do
        (
            try (delete newObjects) catch()
            throw ("Forest Geometry already contains asset: " + sourceNode.name)
        )

        if sourceNode.parent == undefined do (try (sourceNode.position = [0,0,0]) catch())

        prepareReferenceNode sourceNode

        local currentCount = if isProperty forestNode #cobjlist then forestNode.cobjlist.count else 0
        local newIndex = currentCount + 1
        local dimensions = setGeometryItemAtIndex forestNode newIndex sourceNode probabilityValue
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
        ",\"geometry_names\":" + namesJson +
        ",\"probabilities\":" + probsJson +
        ",\"units_x\":" + ((if isProperty forestNode #units_x then forestNode.units_x else 0.0) as string) +
        ",\"units_y\":" + ((if isProperty forestNode #units_y then forestNode.units_y else 0.0) as string) +
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
        local targetZ = units.decodeValue "-1500mm"

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

        -- Layer visibility off. Do not hide the Forest object itself.
        try (refLayer.on = false) catch()

        true
    ),

    fn normalizeReferenceSourcesJson =
    (
        local forestNode = findStage3Forest()
        if forestNode == undefined do
            throw "No Forest Pack object exists in the scene."
        if not (isProperty forestNode #cobjlist) do
            throw "Forest Pack property missing: cobjlist."

        local refLayer = getOrCreateReferenceLayer()
        local targetZ = units.decodeValue "-1500mm"
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
        ",\"maxdensity\":" + ((if isProperty forestNode #maxdensity then forestNode.maxdensity else -1) as string) + "}"
    ),

    fn handleCommand rawCommand =
    (
        local cleanCommand = trimLeft (trimRight rawCommand)
        local command = toUpper cleanCommand

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
