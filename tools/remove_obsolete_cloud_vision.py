from pathlib import Path

obsolete = [
    Path("src/forest_manager/reference_analysis/openai_semantic_provider.py"),
    Path("src/forest_manager/reference_analysis/live_reference_service.py"),
    Path("src/forest_manager/app/live_vision_stage4k.py"),
]

for path in obsolete:
    if path.exists():
        path.unlink()
        print("Removed obsolete cloud file:", path)
