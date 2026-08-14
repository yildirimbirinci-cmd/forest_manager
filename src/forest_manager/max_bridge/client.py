from __future__ import annotations

import socket
from typing import Optional

from forest_manager.core.config import MaxBridgeConfig
from forest_manager.max_bridge.protocol import BridgeProtocolError, BridgeResponse


class MaxBridgeConnectionError(RuntimeError):
    pass


class MaxBridgeClient:
    def __init__(self, config: Optional[MaxBridgeConfig] = None) -> None:
        self.config = config or MaxBridgeConfig()

    def _request(self, command: str) -> BridgeResponse:
        wire_command = command.strip().upper()
        if not wire_command or "\n" in wire_command or "\r" in wire_command:
            raise ValueError("Command must be a single non-empty line.")

        try:
            with socket.create_connection(
                (self.config.host, self.config.port),
                timeout=self.config.timeout_seconds,
            ) as sock:
                sock.settimeout(self.config.timeout_seconds)
                sock.sendall((wire_command + "\n").encode("ascii"))
                reader = sock.makefile("rb")
                raw = reader.readline(1024 * 1024)
        except (OSError, socket.timeout) as exc:
            raise MaxBridgeConnectionError(
                f"Could not connect to 3ds Max bridge at "
                f"{self.config.host}:{self.config.port}: {exc}"
            ) from exc

        if not raw:
            raise MaxBridgeConnectionError(
                "3ds Max bridge closed the connection without a response."
            )

        try:
            line = raw.decode("utf-8").rstrip("\r\n")
        except UnicodeDecodeError as exc:
            raise BridgeProtocolError("Bridge response is not valid UTF-8.") from exc

        return BridgeResponse.from_line(line)

    def ping(self) -> BridgeResponse:
        return self._request("PING")

    def get_selection(self) -> BridgeResponse:
        return self._request("GET_SELECTION")

    def get_forestpack_info(self) -> BridgeResponse:
        return self._request("GET_FORESTPACK_INFO")

    def create_forest_from_selection(self) -> BridgeResponse:
        return self._request("CREATE_FOREST_FROM_SELECTION")

    def get_forest_geometry_contract(self) -> BridgeResponse:
        return self._request("GET_FOREST_GEOMETRY_CONTRACT")

    def get_forest_geometry_contract_details(self) -> BridgeResponse:
        return self._request("GET_FOREST_GEOMETRY_CONTRACT_DETAILS")

    def add_selected_geometry_to_forest(self) -> BridgeResponse:
        return self._request("ADD_SELECTED_GEOMETRY_TO_FOREST")

    def get_forest_distribution_contract(self) -> BridgeResponse:
        return self._request("GET_FOREST_DISTRIBUTION_CONTRACT")

    def get_forest_distribution_units(self) -> BridgeResponse:
        return self._request("GET_FOREST_DISTRIBUTION_UNITS")

    def configure_adaptive_distribution(self) -> BridgeResponse:
        return self._request("CONFIGURE_ADAPTIVE_DISTRIBUTION")

    def normalize_forest_build_state(self) -> BridgeResponse:
        return self._request("NORMALIZE_FOREST_BUILD_STATE")

    def get_forest_full_runtime_contract(self) -> BridgeResponse:
        return self._request("GET_FOREST_FULL_RUNTIME_CONTRACT")

    def normalize_geometry_item(self) -> BridgeResponse:
        return self._request("NORMALIZE_GEOMETRY_ITEM")
