# Stage 5C.1 - Idempotent Scene Management

Goal:
repeated VS Code / Forest Manager apply tests must not accumulate duplicate
Forest Manager source objects when 3ds Max is not reset.

Ownership policy:

- Forest Manager-created T2 merge nodes receive:
  - ForestManagerOwned = true
  - ForestManagerRole = merged_asset_node / reference_source
- All Forest Manager merge nodes are placed in FM_References.
- FM_References remains hidden.
- On RESET_MANAGED_FOREST_FROM_SELECTION:
  1. collect the old FM_Forest_001 cobjlist references,
  2. delete only the managed FM_Forest_001,
  3. delete nodes explicitly marked ForestManagerOwned,
  4. also delete direct legacy cobjlist source references from older builds,
  5. preserve the selected spline and unrelated user scene objects,
  6. create the new clean FM_Forest_001.

The reset response now includes:

    managed_references_deleted

This makes repeated apply runs observable and testable.

Bridge version: 0.9.4

Acceptance test:
run the same Stage 5B apply command multiple times without resetting the Max
scene. The count of managed reference nodes must remain stable instead of
growing every run.
