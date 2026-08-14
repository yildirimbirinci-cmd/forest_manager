# Stage 3G - Full Runtime Contract

Read-only final diagnostic for the Forest Pack 9.4.0 integration.

It dumps every ArrayParameter with count/first value plus build/display/runtime scalar state.
It does not modify or save the scene.

Run after reloading the updated bridge:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.forest_full_runtime_contract_probe

Send the complete `Forest Full Runtime Contract` JSON.
