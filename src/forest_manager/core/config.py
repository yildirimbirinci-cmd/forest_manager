from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MaxBridgeConfig:
    host: str = "127.0.0.1"
    port: int = 49491
    timeout_seconds: float = 3.0
