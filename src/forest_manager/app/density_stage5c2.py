from __future__ import annotations

import argparse
import json
import socket
import sys


def send_command(command: str, host: str = "127.0.0.1", port: int = 49491) -> dict:
    with socket.create_connection((host, port), timeout=10.0) as sock:
        sock.sendall((command + "\n").encode("utf-8"))
        buffer = bytearray()
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buffer.extend(chunk)
            if b"\n" in chunk:
                break
    raw = bytes(buffer).decode("utf-8", errors="replace").strip()
    if not raw:
        raise RuntimeError("3ds Max bridge returned an empty response.")
    return json.loads(raw)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply a physical Forest Pack spacing in meters."
    )
    parser.add_argument("--spacing", type=float, default=0.75)
    args = parser.parse_args()

    if args.spacing <= 0:
        print("Stage 5C.2 error: spacing must be greater than zero meters.")
        return 2

    try:
        response = send_command(f"SET_PHYSICAL_SPACING|{args.spacing:.6f}")
    except Exception as exc:
        print("Stage 5C.2 error:", type(exc).__name__ + ": " + str(exc))
        return 3

    print("Forest Manager Stage 5C.2 Physical Spacing:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    if not response.get("ok"):
        print("Stage 5C.2 bridge rejected physical spacing.")
        return 4

    data = response.get("data") or {}
    if not data.get("verified"):
        print("Stage 5C.2 physical spacing verification failed.")
        return 5

    spacing_system_units = float(data.get("spacing_system_units") or 0.0)
    units_x = float(data.get("units_x") or 0.0)
    units_y = float(data.get("units_y") or 0.0)

    if spacing_system_units <= 0.0 or units_x <= 0.0 or units_y <= 0.0:
        print("Stage 5C.2 physical spacing verification failed: non-positive units.")
        return 6

    print("Stage 5C.2 physical spacing calibration passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
