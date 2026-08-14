# Stage 4G.2 - Reference Source Organization

All T2 source nodes used only as Forest Pack Geometry references are organized in:

    FM_References

Rules:

- Source node Z position: -1500 mm.
- FM_References layer visibility: OFF.
- Forest object and Area spline remain visible and are not moved.
- Existing Forest Geometry sources can be normalized with one command.
- Newly merged/appended T2 sources automatically use the same policy.

The bridge uses:

    units.decodeValue "-1500mm"

so the requested -1500 mm position is independent of the scene's current system-unit scale.

Run:

    ForestManagerBridge.stop()

Reload the updated bridge, then:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.t2_reference_sources_stage4g2_smoke

Expected:

    Stage 4G.2 reference-source organization acceptance passed.

Verify in Scene Explorer / Layer Explorer:

- FM_References exists.
- T2 source CProxy nodes are inside FM_References.
- Layer visibility is off.
- Source nodes are at Z = -1500 mm.
