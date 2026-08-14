from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .local_hardware_profiler import LocalVisionHardwareProfiler
from .local_model_verifier import LocalModelVerifier
from .smolvlm500m_local_backend import SmolVLM500MLocalBackend


@dataclass(frozen=True)
class LocalVisionBundleReadiness:
    hardware: dict[str, Any]
    model: dict[str, Any]
    runtime_ready: bool
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "hardware": self.hardware,
            "model": self.model,
            "runtime_ready": self.runtime_ready,
            "blockers": list(self.blockers),
        }


class LocalVisionBundleVerifier:
    def inspect(self) -> LocalVisionBundleReadiness:
        hardware = LocalVisionHardwareProfiler().inspect()
        backend = SmolVLM500MLocalBackend()
        model = LocalModelVerifier(backend.config.model_dir).inspect()

        blockers: list[str] = []

        if not hardware.torch_available:
            blockers.append("torch_missing")
        if not hardware.transformers_available:
            blockers.append("transformers_missing")
        if not hardware.pillow_available:
            blockers.append("pillow_missing")
        if not model.manifest_exists:
            blockers.append("model_manifest_missing")
        if not model.config_exists:
            blockers.append("model_config_missing")
        if not model.weights_exist:
            blockers.append("model_weights_missing")
        if not model.processor_exists:
            blockers.append("model_processor_missing")

        runtime_ready = len(blockers) == 0

        return LocalVisionBundleReadiness(
            hardware=hardware.to_dict(),
            model=model.to_dict(),
            runtime_ready=runtime_ready,
            blockers=tuple(blockers),
        )
