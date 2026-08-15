from __future__ import annotations

import base64
import socket
from typing import Optional

from forest_manager.core.config import MaxBridgeConfig
from forest_manager.max_bridge.protocol import BridgeProtocolError, BridgeResponse


class MaxBridgeConnectionError(RuntimeError):
    pass


class MaxBridgeClient:
    def __init__(self, config: Optional[MaxBridgeConfig] = None) -> None:
        self.config = config or MaxBridgeConfig()

    def _request_wire(self, wire_command: str) -> BridgeResponse:
        wire_command = wire_command.strip()
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

    def _request(self, command: str) -> BridgeResponse:
        return self._request_wire(command.strip().upper())

    def ping(self) -> BridgeResponse:
        return self._request("PING")

    def get_selection(self) -> BridgeResponse:
        return self._request("GET_SELECTION")

    def get_forestpack_info(self) -> BridgeResponse:
        return self._request("GET_FORESTPACK_INFO")

    def create_forest_from_selection(self) -> BridgeResponse:
        return self._request("CREATE_FOREST_FROM_SELECTION")

    def reset_managed_forest_from_selection(self) -> BridgeResponse:
        return self._request("RESET_MANAGED_FOREST_FROM_SELECTION")

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

    def merge_t2_asset_and_bind(self, asset_path: str) -> BridgeResponse:
        raw_path = str(asset_path).strip()
        if not raw_path:
            raise ValueError("Asset path must not be empty.")
        encoded = base64.b64encode(raw_path.encode("utf-8")).decode("ascii")
        return self._request_wire("MERGE_T2_ASSET|" + encoded)

    def configure_asset_aware_density(self) -> BridgeResponse:
        return self._request("CONFIGURE_ASSET_AWARE_DENSITY")

    def configure_target_item_density(self) -> BridgeResponse:
        return self._request("CONFIGURE_TARGET_ITEM_DENSITY")

    def configure_fixed_distribution_units(self) -> BridgeResponse:
        return self._request("CONFIGURE_FIXED_DISTRIBUTION_UNITS")

    def append_t2_asset_geometry(self, asset_path: str, probability: float = 50.0) -> BridgeResponse:
        raw_path = str(asset_path).strip()
        if not raw_path:
            raise ValueError("Asset path must not be empty.")
        prob = float(probability)
        if prob <= 0.0 or prob > 100.0:
            raise ValueError("Probability must be in the range (0, 100].")
        encoded = base64.b64encode(raw_path.encode("utf-8")).decode("ascii")
        return self._request_wire("APPEND_T2_ASSET|" + encoded + "|" + format(prob, ".6f"))

    def set_geometry_probabilities(self, probabilities: list[float]) -> BridgeResponse:
        if not probabilities:
            raise ValueError("At least one probability is required.")
        values = [float(value) for value in probabilities]
        if any(value <= 0.0 for value in values):
            raise ValueError("All probabilities must be greater than zero.")
        payload = ",".join(format(value, ".6f") for value in values)
        return self._request_wire("SET_GEOMETRY_PROBABILITIES|" + payload)

    def normalize_reference_sources(self) -> BridgeResponse:
        return self._request("NORMALIZE_REFERENCE_SOURCES")

    def get_forest_geometry_summary(self) -> BridgeResponse:
        return self._request("GET_FOREST_GEOMETRY_SUMMARY")
