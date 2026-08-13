import json
import socket
import threading

from forest_manager.core.config import MaxBridgeConfig
from forest_manager.max_bridge.client import MaxBridgeClient


def _serve_once(listener, expected_command, response):
    conn, _ = listener.accept()
    with conn:
        reader = conn.makefile("rb")
        command = reader.readline().decode("ascii").strip()
        assert command == expected_command
        conn.sendall((json.dumps(response) + "\n").encode("utf-8"))


def test_ping_round_trip():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    response = {
        "ok": True,
        "command": "PING",
        "data": {"max_year": 2020, "bridge_version": "0.1.0"},
        "error": "",
    }

    thread = threading.Thread(
        target=_serve_once,
        args=(listener, "PING", response),
        daemon=True,
    )
    thread.start()

    client = MaxBridgeClient(
        MaxBridgeConfig(host="127.0.0.1", port=port, timeout_seconds=1.0)
    )
    result = client.ping()

    thread.join(timeout=2.0)
    listener.close()

    assert result.ok is True
    assert result.data["max_year"] == 2020
