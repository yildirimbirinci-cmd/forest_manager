from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


class LocalVisionBackendError(RuntimeError):
    pass


@runtime_checkable
class LocalVisionBackend(Protocol):
    @property
    def name(self) -> str:
        ...

    def is_available(self) -> bool:
        ...

    def analyze(
        self,
        image_path: str,
        prompt: str,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class LocalVisionModelConfig:
    model_dir: Path
    backend: str = "transformers"
    max_new_tokens: int = 768

    @classmethod
    def default(cls) -> "LocalVisionModelConfig":
        return cls(model_dir=Path("models/vision").resolve())

    def validate(self) -> None:
        if not self.model_dir.exists():
            raise LocalVisionBackendError(
                f"Local vision model directory does not exist: {self.model_dir}"
            )
        if not self.model_dir.is_dir():
            raise LocalVisionBackendError(
                f"Local vision model path is not a directory: {self.model_dir}"
            )
