# Stage 5D.24 - Controlled UV Clamp Preview

Viewport evidence from Stage 5D.23 shows periodic repetition of the generated
species mask patterns.

The live StandardUVGen contract reports:
- U_Tile = true
- V_Tile = true
- U_Tiling = 1.0
- V_Tiling = 1.0
- Real World Scale = true

This diagnostic stage tests only whether disabling U/V tiling removes the
visible periodic repetition.

Apply mode:
- FM_Forest_001 disabled temporarily
- only foreground species layer enabled
- U_Tile = false
- V_Tile = false
- Density Units remains exactly 75.0 m X/Y
- no map, offset, tiling factor, cluster or transform value is changed

Rollback mode:
- U_Tile/V_Tile restored to true
- FM_Forest_001 active
- all three species layers disabled

This is a visual diagnostic, not the final alignment solution.

Bridge version: 0.9.38
