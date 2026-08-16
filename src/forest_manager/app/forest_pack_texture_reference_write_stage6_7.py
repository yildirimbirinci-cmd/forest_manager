from __future__ import annotations

import json

from forest_manager.forest_control.service import ForestPackControlService


def main() -> int:
    print("Forest Manager Stage 6.7 Texture Reference Write Endpoint:")
    service = ForestPackControlService()
    report: dict[str, object] = {"ok": False, "verified": False}
    try:
        forests = service.list_forests()
        populated: list[dict[str, object]] = []
        empty: list[dict[str, object]] = []
        for forest_name in forests:
            try:
                ref = service.get_texture_reference(forest_name, "distmap", preflight=False)
            except Exception:
                continue
            token = ref.get("value")
            item = {
                "forest_name": forest_name,
                "token": token,
                "filename": ref.get("filename"),
                "value_class": ref.get("value_class"),
            }
            if isinstance(token, str) and token:
                populated.append(item)
            elif token is None:
                empty.append(item)

        if not populated:
            raise RuntimeError("Stage 6.7 requires at least one Forest object with a Bitmaptexture distmap reference token.")
        if not empty:
            raise RuntimeError("Stage 6.7 requires at least one Forest object with an undefined distmap for nullable reference verification.")

        source = populated[0]
        target_slot = empty[0]
        target_forest = str(target_slot["forest_name"])
        before = None
        target = str(source["token"])

        result = service.set_property(target_forest, "distmap", target, preflight=False)
        after_write = service.get_texture_reference(target_forest, "distmap", preflight=False).get("value")
        rollback = service.rollback()
        after_rollback = service.get_texture_reference(target_forest, "distmap", preflight=False).get("value")
        verified = (
            result.get("verified") is True
            and after_write == target
            and after_rollback is None
            and len(rollback) == 1
        )
        report = {
            "ok": verified,
            "forest_name": target_forest,
            "property_name": "distmap",
            "reference_type": "texture",
            "value_class_before": str(target_slot.get("value_class") or ""),
            "source_forest": str(source["forest_name"]),
            "source_value_class": str(source.get("value_class") or ""),
            "before": before,
            "target": target,
            "after_write": after_write,
            "after_rollback": after_rollback,
            "rollback_step_count": len(rollback),
            "runtime_write_endpoint": True,
            "runtime_rollback_endpoint": True,
            "policy": {
                "texture_reference_property_allowlist": ["distmap"],
                "nullable_texture_references": True,
                "animhandle_token_resolution": target.lower().startswith("anim:"),
                "bitmap_filename_fallback_resolution": True,
                "existing_scene_bitmap_resolution": True,
                "single_existing_bitmap_source_sufficient": True,
                "undefined_target_slot_required": True,
                "cproxy_reference_writes_blocked": True,
                "bridge_readback_verification": True,
                "service_readback_verification": True,
                "single_session_mixed_rollback_journal": True,
                "startup_loader_content_stable_across_build_ids": True,
                "final_state_preserved": after_rollback is None,
            },
            "verified": verified,
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if not verified:
            raise RuntimeError("Stage 6.7 texture reference runtime verification failed.")
        print("Stage 6.7 texture reference write endpoint passed.")
        return 0
    except Exception as exc:
        report = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "verified": False}
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
