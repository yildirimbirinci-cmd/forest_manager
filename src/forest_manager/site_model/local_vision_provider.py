from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib import request


DEFAULT_MODEL_ID = "Qwen3-VL-4B-Instruct-Q4_K_M"
DEFAULT_ENDPOINT = "http://127.0.0.1:8089/v1/chat/completions"

_ALLOWED_NATURALNESS = {"Ordered", "Balanced", "Natural", "Wild"}
_ALLOWED_CLUSTERS = {"Individual", "Solitary", "Small Groups", "Medium Clusters", "Large Masses"}


@dataclass(frozen=True)
class LocalVisionResult:
    provider: str
    model: str
    groups: tuple[dict[str, Any], ...]


class LocalVisionProviderError(RuntimeError):
    pass


class LocalVisionProvider:
    """Loopback-only Qwen vision client for Forest Manager.

    The provider performs no scene mutation. It only converts a reference image
    into variable-count semantic Plant Group intents. Asset identity remains a
    later T2-library responsibility.
    """

    def __init__(
        self,
        *,
        endpoint: str = DEFAULT_ENDPOINT,
        model_id: str = DEFAULT_MODEL_ID,
        timeout_seconds: float = 120.0,
        transport: Callable[[str, bytes, float], dict[str, Any]] | None = None,
    ) -> None:
        if not endpoint.startswith("http://127.0.0.1:") and not endpoint.startswith("http://localhost:"):
            raise ValueError("Forest Manager local vision provider must use a loopback endpoint.")
        self.endpoint = endpoint
        self.model_id = model_id
        self.timeout_seconds = float(timeout_seconds)
        self._transport = transport or self._post_json

    @staticmethod
    def _prompt() -> str:
        return """Analyze this landscape reference image for Forest Manager.\n\nReturn ONLY valid JSON. No markdown. No explanation.\n\nSchema:\n{\n  \"groups\": [\n    {\n      \"label\": \"short human-readable group name\",\n      \"semantic_role\": \"foreground_mass|mid_accent|purple_accent|flower_accent|structural_shrub|ornamental_grass|tree_canopy|groundcover|other\",\n      \"coverage_weight\": 0.0,\n      \"naturalness\": \"Ordered|Balanced|Natural\",\n      \"cluster_character\": \"Individual|Small Groups|Medium Clusters|Large Masses\",\n      \"confidence\": 0.0,\n      \"species_candidates\": [{\"name\": \"visual species hypothesis\", \"confidence\": 0.0}]\n    }\n  ]\n}\n\nRules:\n- Detect visually distinct designed planting groups actually present.\n- Group count is variable; never force exactly 3 or 5 groups.\n- coverage_weight values should approximately sum to 1.0.\n- Do not include unrelated background vegetation as a planting-bed group.\n- Prefer useful landscape-design groups over tiny isolated details.\n- Every group except semantic_role=other must include 1 to 3 non-empty species_candidates.\n- When species identity is ambiguous, provide multiple plausible alternatives instead of leaving species_candidates empty.\n- Keep growth form consistent with semantic_role: structural_shrub candidates must be shrubs, tree_canopy candidates must be trees, groundcover candidates must be low groundcovers, and ornamental_grass candidates must be grasses.\n- Prefer recognizable botanical/common plant names useful for matching a real asset library; include genus/species names when visually plausible.\n- Species candidates are visual hypotheses only. Do not claim certainty where ambiguous.\n- confidence values are from 0.0 to 1.0.\n"""

    @staticmethod
    def _post_json(endpoint: str, body: bytes, timeout_seconds: float) -> dict[str, Any]:
        req = request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:
                payload = response.read().decode("utf-8")
        except Exception as exc:
            raise LocalVisionProviderError(f"Local vision request failed: {exc}") from exc
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise LocalVisionProviderError("Local vision server returned invalid JSON.") from exc
        if not isinstance(parsed, dict):
            raise LocalVisionProviderError("Local vision server response must be a JSON object.")
        return parsed

    @staticmethod
    def _extract_content(response: dict[str, Any]) -> str:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LocalVisionProviderError("Local vision response has no assistant content.") from exc
        text = str(content or "").strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    @staticmethod
    def _normalize_groups(payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
        raw_groups = payload.get("groups")
        if not isinstance(raw_groups, list) or not raw_groups:
            raise LocalVisionProviderError("Local vision result contains no Plant Groups.")

        groups: list[dict[str, Any]] = []
        weights: list[float] = []
        for index, raw in enumerate(raw_groups, start=1):
            if not isinstance(raw, dict):
                continue
            role = str(raw.get("semantic_role") or "other").strip() or "other"
            label = str(raw.get("label") or role.replace("_", " ").title()).strip()
            try:
                weight = max(0.0, float(raw.get("coverage_weight") or 0.0))
            except (TypeError, ValueError):
                weight = 0.0
            try:
                confidence = min(1.0, max(0.0, float(raw.get("confidence") or 0.0)))
            except (TypeError, ValueError):
                confidence = 0.0
            naturalness = str(raw.get("naturalness") or "Balanced").strip()
            if naturalness not in _ALLOWED_NATURALNESS:
                naturalness = "Balanced"
            cluster = str(raw.get("cluster_character") or "Medium Clusters").strip()
            if cluster not in _ALLOWED_CLUSTERS:
                cluster = "Medium Clusters"

            candidates = raw.get("species_candidates") or []
            source_names: list[str] = []
            if isinstance(candidates, list):
                ranked: list[tuple[float, str]] = []
                for candidate in candidates:
                    if not isinstance(candidate, dict):
                        continue
                    name = str(candidate.get("name") or "").strip()
                    if not name:
                        continue
                    try:
                        candidate_confidence = min(1.0, max(0.0, float(candidate.get("confidence") or 0.0)))
                    except (TypeError, ValueError):
                        candidate_confidence = 0.0
                    ranked.append((candidate_confidence, name))
                ranked.sort(key=lambda item: (-item[0], item[1].casefold()))
                source_names = [name for _score, name in ranked]

            groups.append({
                "semantic_role": role,
                "label": label,
                "coverage_weight": weight,
                "naturalness": naturalness,
                "cluster_character": cluster,
                "confidence": confidence,
                "source_names": source_names,
                "species_candidates": candidates if isinstance(candidates, list) else [],
                "provider_group_index": index,
            })
            weights.append(weight)

        if not groups:
            raise LocalVisionProviderError("Local vision result contains no valid Plant Groups.")
        total = sum(weights)
        if total <= 0.0:
            equal = 1.0 / float(len(groups))
            for group in groups:
                group["coverage_weight"] = equal
        else:
            for group in groups:
                group["coverage_weight"] = float(group["coverage_weight"] / total)
        return tuple(groups)

    @staticmethod
    def _refinement_prompt(first_groups: tuple[dict[str, Any], ...]) -> str:
        compact = [
            {
                "label": group.get("label"),
                "semantic_role": group.get("semantic_role"),
                "coverage_weight": group.get("coverage_weight"),
                "naturalness": group.get("naturalness"),
                "cluster_character": group.get("cluster_character"),
                "confidence": group.get("confidence"),
                "species_candidates": group.get("species_candidates"),
            }
            for group in first_groups
        ]
        return (
            "Audit and refine this first-pass Forest Manager planting-group analysis against the same image.\n\n"
            "Return ONLY valid JSON using exactly the same schema with a top-level groups array.\n"
            "Do not add decorative/background groups that are not actually part of the designed planting.\n"
            "Keep the group count stable unless two groups are clearly duplicates.\n"
            "Every group except semantic_role=other must contain 1 to 3 non-empty species_candidates.\n"
            "When identification is uncertain, provide multiple plausible alternatives instead of an empty list.\n"
            "Growth form must agree with semantic_role: shrubs as structural_shrub, trees as tree_canopy, "
            "low plants as groundcover, grasses as ornamental_grass, and flowering herbaceous plants as flower accents.\n"
            "If the first pass paired a species with the wrong growth-form role, correct the role or the species candidates.\n"
            "Prefer botanical/common names that can be matched against a real 3D plant asset library.\n"
            "Do not claim certainty; use confidence values.\n\n"
            "First-pass JSON:\n" + json.dumps({"groups": compact}, ensure_ascii=True)
        )

    @staticmethod
    def _audit_refined_groups(groups: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
        """Return unresolved non-other group labels without aborting the full vision result.

        Refinement is best-effort. Groups that still have no species candidates
        remain in the AI result and are excluded later by the existing T2
        resolution contract as ``no_species_candidates``. One unresolved group
        must not discard otherwise valid resolved groups.
        """
        return tuple(
            str(group.get("label") or group.get("semantic_role") or "group")
            for group in groups
            if str(group.get("semantic_role") or "").strip() != "other"
            and not tuple(group.get("source_names") or ())
        )

    def _request_groups(self, *, image_data: str, mime: str, prompt: str, temperature: float) -> tuple[dict[str, Any], ...]:
        body = {
            "model": self.model_id,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_data}"}},
                ],
            }],
            "temperature": float(temperature),
            "max_tokens": 2200,
        }
        response = self._transport(
            self.endpoint,
            json.dumps(body, ensure_ascii=True).encode("utf-8"),
            self.timeout_seconds,
        )
        content = self._extract_content(response)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LocalVisionProviderError("Vision model did not return valid Plant Group JSON.") from exc
        if not isinstance(parsed, dict):
            raise LocalVisionProviderError("Vision model Plant Group result must be a JSON object.")
        return self._normalize_groups(parsed)

    def analyze(self, image_path: str) -> LocalVisionResult:
        path = Path(image_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Reference image does not exist: {path}")
        mime = "image/png" if path.suffix.casefold() == ".png" else "image/jpeg"
        image_data = base64.b64encode(path.read_bytes()).decode("ascii")

        first_groups = self._request_groups(
            image_data=image_data,
            mime=mime,
            prompt=self._prompt(),
            temperature=0.1,
        )
        refined_groups = self._request_groups(
            image_data=image_data,
            mime=mime,
            prompt=self._refinement_prompt(first_groups),
            temperature=0.05,
        )
        self._audit_refined_groups(refined_groups)
        return LocalVisionResult(
            provider="forest_manager_local",
            model=self.model_id,
            groups=refined_groups,
        )
