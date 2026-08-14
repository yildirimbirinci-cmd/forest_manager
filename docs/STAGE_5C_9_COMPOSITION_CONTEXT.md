# Stage 5C.9 - Composition Context

Purpose:
combine the verified active-scene measurements needed by the later composition engine without changing the 3ds Max scene.

GET_COMPOSITION_CONTEXT reports:
- active scene Unit Setup;
- selected closed spline real area;
- current Forest Geometry names/classes/probabilities;
- current Forest Density in internal system units, active display units, and canonical meters;
- generated-item probe for diagnostics only.

This stage is read-only. It does not modify density, probabilities, geometry, spline, or reference sources.

For the current acceptance scene, the expected context is approximately 7528.88 m2 area and 75.0 m Forest Density Units, but those values are read from the active scene and are not hard-coded.

Bridge version: 0.9.18
