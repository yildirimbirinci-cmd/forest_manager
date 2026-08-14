# Stage 4H - Composition Plan Engine

Stage 4H is the transition from hard-coded smoke tests to the application architecture.

A composition is now represented by JSON:

    {
      "name": "...",
      "items": [
        {"query": "Acer campestre (Field maple)", "weight": 40},
        {"query": "Alnus glutinosa (Black alder)", "weight": 35},
        {"query": "Alnus x spaethii 'Spaeth' (Spaeth alder)", "weight": 25}
      ]
    }

The engine:

1. Resolves each query against the real T2 library.
2. Rejects duplicate resolutions.
3. Reads the current Forest Geometry List.
4. Skips assets already present.
5. Merges only missing assets.
6. Rejects unmanaged Geometry items rather than silently deleting them.
7. Applies probabilities in the actual Forest Geometry order.
8. Normalizes reference sources into `FM_References`.
9. Keeps the reference layer hidden and sources at -1500 mm.

This JSON schema is the future boundary for:
- GUI controls,
- reference-image analysis,
- saved presets,
- AI-generated landscape composition plans.

## Run

Stop/reload the bridge:

    ForestManagerBridge.stop()

Then:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.composition_plan_stage4h_smoke

Expected:

    Stage 4H composition-plan acceptance passed.
