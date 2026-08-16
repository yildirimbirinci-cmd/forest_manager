from __future__ import annotations

import argparse
import json
import sys

from forest_manager.composition.semantic_probability_plan import build_probability_plan
from forest_manager.max_bridge.runtime_bridge import ensure_current_bridge, send_command


DEFAULT_TEXT = "PLANTS: lavender purple white lillies flowers shrubs plants."


def _context() -> dict:
    response = send_command("GET_COMPOSITION_CONTEXT")
    if not response.get("ok"):
        raise RuntimeError("Composition context failed: " + json.dumps(response, ensure_ascii=False))
    return response.get("data") or {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Forest Manager Stage 5D.1 semantic probability planner")
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    try:
        ensure_current_bridge()
        before = _context()
        geometry = before.get("geometry") or {}
        names = list(geometry.get("geometry_names") or [])
        plan = build_probability_plan(args.text, names)

        report = {
            "mode": "apply" if args.apply else "preview",
            "plan": plan,
            "density_before": before.get("density") or {},
            "applied": False,
        }

        if args.apply:
            values = ",".join(str(value) for value in plan["probabilities"])
            response = send_command("SET_GEOMETRY_PROBABILITIES|" + values)
            if not response.get("ok"):
                raise RuntimeError("Probability apply failed: " + json.dumps(response, ensure_ascii=False))

            after = _context()
            density_before = before.get("density") or {}
            density_after = after.get("density") or {}
            if density_after.get("units_x_system") != density_before.get("units_x_system"):
                raise RuntimeError("Density changed while applying semantic probabilities (X).")
            if density_after.get("units_y_system") != density_before.get("units_y_system"):
                raise RuntimeError("Density changed while applying semantic probabilities (Y).")

            applied_probs = list(((after.get("geometry") or {}).get("probabilities") or []))
            if len(applied_probs) != len(plan["probabilities"]):
                raise RuntimeError("Applied probability count mismatch.")

            report["applied"] = True
            report["apply_response"] = response.get("data") or {}
            report["density_after"] = density_after
            report["composition_after"] = after

        print("Forest Manager Stage 5D.1 Semantic Composition Probabilities:")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if args.apply:
            print("Stage 5D.1 semantic probability apply passed.")
        else:
            print("Stage 5D.1 semantic probability preview passed.")
        return 0
    except Exception as exc:
        print("Stage 5D.1 error:", type(exc).__name__ + ": " + str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
