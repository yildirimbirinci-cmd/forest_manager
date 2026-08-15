# Stage 5D.14.2 - LayerProperties.nodes Out-Parameter Fix

Root cause:
`LayerProperties.nodes` is a MAXScript interface method with a by-reference
output array. It cannot be consumed as a normal property.

Incorrect:
    local layerNodes = refsLayer.nodes

Correct:
    local layerNodes = #()
    refsLayer.nodes &layerNodes

This follows Autodesk's documented LayerProperties interface contract.

The live source/area contract probe remains read-only.

Bridge version: 0.9.29
