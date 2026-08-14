# Stage 3D - Distribution Units Probe

Read-only probe for Forest Pack 9.4.0 distribution density/unit properties.

Run after loading the updated bridge:

    $env:PYTHONPATH = "$PWD\src"
    python -m forest_manager.app.forest_distribution_units_probe

Send the complete `Forest Distribution Units` output.
No scene mutation is performed.
