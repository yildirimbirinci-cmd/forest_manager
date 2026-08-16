from __future__ import annotations

import argparse
import json
import sys


from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


def main() -> int:
    parser = argparse.ArgumentParser(description="Set Forest Pack Density Units in meters.")
    parser.add_argument("--density-m", type=float, default=75.0)
    args = parser.parse_args()

    if args.density_m <= 0:
        print("Stage 5C.3.2 error: density-m must be greater than zero.")
        return 2

    try:
        ensure_current_bridge()
        response = send_command(f"SET_DENSITY_METERS|{args.density_m:.6f}")
    except Exception as exc:
        print("Stage 5C.3.2 error:", type(exc).__name__ + ": " + str(exc))
        return 3

    print("Forest Manager Stage 5C.3.2 Density Calibration:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        print("Stage 5C.3.2 bridge rejected density calibration.")
        return 4

    data = response.get("data") or {}
    if not data.get("verified"):
        print("Stage 5C.3.2 density verification failed.")
        return 5

    expected = float(data.get("one_meter_system_units") or 0.0) * args.density_m
    actual = float(data.get("density_system_units") or 0.0)
    units_x = float(data.get("units_x") or 0.0)
    units_y = float(data.get("units_y") or 0.0)
    if expected <= 0.0 or abs(actual - expected) > 0.001:
        print("Stage 5C.3.2 density verification failed: conversion mismatch.")
        return 6
    if abs(units_x - expected) > 0.001 or abs(units_y - expected) > 0.001:
        print("Stage 5C.3.2 density verification failed: Forest units mismatch.")
        return 7

    print("Stage 5C.3.2 density calibration passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
