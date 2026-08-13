from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict


class BridgeProtocolError(RuntimeError):
    pass


@dataclass(frozen=True)
class BridgeResponse:
    ok: bool
    command: str
    data: Dict[str, Any]
    error: str = ""

    @classmethod
    def from_line(cls, line: str) -> "BridgeResponse":
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BridgeProtocolError(f"Invalid JSON response: {exc}") from exc

        if not isinstance(payload, dict):
            raise BridgeProtocolError("Bridge response must be a JSON object.")

        ok = payload.get("ok")
        command = payload.get("command", "")
        data = payload.get("data", {})
        error = payload.get("error", "")

        if not isinstance(ok, bool):
            raise BridgeProtocolError("Bridge response field 'ok' must be boolean.")
        if not isinstance(command, str):
            raise BridgeProtocolError("Bridge response field 'command' must be string.")
        if not isinstance(data, dict):
            raise BridgeProtocolError("Bridge response field 'data' must be object.")
        if not isinstance(error, str):
            raise BridgeProtocolError("Bridge response field 'error' must be string.")

        return cls(ok=ok, command=command, data=data, error=error)
