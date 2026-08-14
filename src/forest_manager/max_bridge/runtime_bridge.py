from __future__ import annotations

import base64
import json
import socket
import time
from pathlib import Path

HOST = "127.0.0.1"
PORT = 49491
EXPECTED_BRIDGE_VERSION = "0.9.20"


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def send_command(command: str, timeout: float = 10.0) -> dict:
    with socket.create_connection((HOST, PORT), timeout=timeout) as sock:
        sock.sendall((command + "\n").encode("utf-8"))
        data = bytearray()
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            data.extend(chunk)
            if b"\n" in chunk:
                break
    raw = bytes(data).decode("utf-8", errors="replace").strip()
    if not raw:
        raise RuntimeError("3ds Max bridge returned an empty response.")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Invalid JSON from 3ds Max bridge: " + raw) from exc


def current_version() -> str:
    ping = send_command("PING", timeout=1.5)
    if not ping.get("ok"):
        return ""
    return str((ping.get("data") or {}).get("bridge_version") or "")


def reload_current_bridge() -> dict:
    bridge_path = project_root() / "maxscripts" / "ForestManager_Bridge.ms"
    if not bridge_path.is_file():
        raise RuntimeError("Forest Manager bridge file not found: " + str(bridge_path))

    encoded = base64.b64encode(str(bridge_path).encode("utf-8")).decode("ascii")
    response = send_command("RELOAD_BRIDGE|" + encoded, timeout=5.0)
    if not response.get("ok"):
        raise RuntimeError("Bridge reload request failed: " + json.dumps(response, ensure_ascii=False))

    last_error = ""
    for _ in range(40):
        time.sleep(0.2)
        try:
            ping = send_command("PING", timeout=1.0)
            version = str((ping.get("data") or {}).get("bridge_version") or "")
            if ping.get("ok") and version == EXPECTED_BRIDGE_VERSION:
                return ping
            last_error = "bridge_version=" + version
        except Exception as exc:
            last_error = type(exc).__name__ + ": " + str(exc)
    raise RuntimeError("Bridge reload did not verify: " + last_error)


def ensure_current_bridge() -> dict:
    try:
        version = current_version()
        if version == EXPECTED_BRIDGE_VERSION:
            return send_command("PING", timeout=1.5)
    except Exception:
        pass

    try:
        return reload_current_bridge()
    except Exception as exc:
        raise RuntimeError(
            "Automatic bridge preflight failed. If this is the first upgrade from a bridge older than 0.9.13, run maxscripts/ForestManager_Bridge.ms once in 3ds Max. Details: " + str(exc)
        ) from exc
