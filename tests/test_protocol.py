import json

import pytest

from forest_manager.max_bridge.protocol import BridgeProtocolError, BridgeResponse


def test_parse_success_response():
    response = BridgeResponse.from_line(
        '{"ok":true,"command":"PING","data":{"max_year":2020},"error":""}'
    )
    assert response.ok is True
    assert response.command == "PING"
    assert response.data["max_year"] == 2020


def test_reject_non_json():
    with pytest.raises(BridgeProtocolError):
        BridgeResponse.from_line("not-json")


def test_reject_wrong_field_types():
    with pytest.raises(BridgeProtocolError):
        BridgeResponse.from_line(
            json.dumps({"ok": "yes", "command": "PING", "data": {}, "error": ""})
        )
