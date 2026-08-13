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


def _round_trip(expected_command, response, method_name):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    thread = threading.Thread(
        target=_serve_once,
        args=(listener, expected_command, response),
        daemon=True,
    )
    thread.start()

    client = MaxBridgeClient(
        MaxBridgeConfig(host="127.0.0.1", port=port, timeout_seconds=1.0)
    )
    result = getattr(client, method_name)()

    thread.join(timeout=2.0)
    listener.close()
    return result


def test_ping_round_trip():
    result = _round_trip(
        "PING",
        {
            "ok": True,
            "command": "PING",
            "data": {"max_year": 2020, "bridge_version": "0.2.0"},
            "error": "",
        },
        "ping",
    )
    assert result.ok is True
    assert result.data["max_year"] == 2020


def test_forestpack_info_round_trip():
    result = _round_trip(
        "GET_FORESTPACK_INFO",
        {
            "ok": True,
            "command": "GET_FORESTPACK_INFO",
            "data": {"available": True, "class_name": "::Forest_Pro", "forest_count": 0},
            "error": "",
        },
        "get_forestpack_info",
    )
    assert result.ok is True
    assert result.data["available"] is True


def test_create_forest_round_trip():
    result = _round_trip(
        "CREATE_FOREST_FROM_SELECTION",
        {
            "ok": True,
            "command": "CREATE_FOREST_FROM_SELECTION",
            "data": {
                "forest_name": "FM_Forest_001",
                "area_count": 1,
                "area_node": "Line001",
                "include": True,
                "verified": True,
            },
            "error": "",
        },
        "create_forest_from_selection",
    )
    assert result.ok is True
    assert result.data["verified"] is True
