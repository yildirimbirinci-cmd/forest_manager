from __future__ import annotations

from dataclasses import dataclass, asdict
import importlib.util
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LocalModelReadiness:
    model_dir: str
    manifest_exists: bool
    config_exists: bool
    weights_exist: bool
    processor_exists: bool
    torch_available: bool
    transformers_available: bool
    pillow_available: bool
    ready: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LocalModelVerifier:
    def __init__(self, model_dir: Path | str):
        self.model_dir = Path(model_dir).resolve()

    @staticmethod
    def _module_exists(name: str) -> bool:
        return importlib.util.find_spec(name) is not None

    def inspect(self) -> LocalModelReadiness:
        manifest_path = self.model_dir / "forest_manager_model.json"
        config_path = self.model_dir / "config.json"

        weights_exist = (
            (self.model_dir / "model.safetensors").exists()
            or (self.model_dir / "model.safetensors.index.json").exists()
        )

        processor_exists = (
            (self.model_dir / "preprocessor_config.json").exists()
            or (self.model_dir / "processor_config.json").exists()
        )

        torch_available = self._module_exists("torch")
        transformers_available = self._module_exists("transformers")
        pillow_available = self._module_exists("PIL")

        ready = all([
            manifest_path.exists(),
            config_path.exists(),
            weights_exist,
            processor_exists,
            torch_available,
            transformers_available,
            pillow_available,
        ])

        return LocalModelReadiness(
            model_dir=str(self.model_dir),
            manifest_exists=manifest_path.exists(),
            config_exists=config_path.exists(),
            weights_exist=weights_exist,
            processor_exists=processor_exists,
            torch_available=torch_available,
            transformers_available=transformers_available,
            pillow_available=pillow_available,
            ready=ready,
        )
