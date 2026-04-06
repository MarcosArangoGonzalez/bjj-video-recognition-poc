from __future__ import annotations

import base64
import json
import re
from collections import defaultdict
from typing import Any

import cv2
import httpx

from app.config import Settings
from app.core.logging import get_logger
from app.schemas.analysis import AnalysisResult
from app.services.knowledge_descriptions import get_detection_details, humanize_label

logger = get_logger(__name__)

MODEL_ALIASES = {
    "gemini-1.5-flash": "gemini-flash-latest",
    "gemini-1.5-flash-latest": "gemini-flash-latest",
}


class GeminiEnrichmentService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.enabled = bool(settings.gemini_enabled and settings.gemini_api_key)

    async def enrich(self, video_source: str, result: AnalysisResult) -> AnalysisResult:
        if not self.enabled or result.status != "completed":
            return result

        try:
            frames = self._sample_video_frames(video_source)
            if not frames:
                return result

            payload = self._build_request_payload(frames, result)
            response = await self._call_gemini(payload)
            detections = self._parse_detections(response)
            if not detections:
                return result
            detections = self._filter_biomechanical_hallucinations(detections)
            detections = self._filter_by_local_support(result, detections)
            if not detections:
                return result
            return self._replace_summary_with_gemini(result, detections)
        except Exception as exc:
            logger.warning("Gemini enrichment failed: %s", exc)
            return result

    def _sample_video_frames(self, video_source: str) -> list[str]:
        capture = cv2.VideoCapture(video_source)
        if not capture.isOpened():
            return []

        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, int(fps * max(self.settings.gemini_sample_interval_seconds, 0.5)))
        frame_index = 0
        sampled: list[str] = []

        try:
            while capture.isOpened() and len(sampled) < self.settings.gemini_max_frames:
                success, frame = capture.read()
                if not success:
                    break
                if frame_index % step != 0:
                    frame_index += 1
                    continue
                success, encoded = cv2.imencode(".jpg", frame)
                if success:
                    sampled.append(base64.b64encode(encoded.tobytes()).decode("ascii"))
                frame_index += 1
        finally:
            capture.release()

        return sampled

    def _build_request_payload(self, frames: list[str], result: AnalysisResult) -> dict[str, Any]:
        prompt = self._build_prompt(result)
        parts: list[dict[str, Any]] = [{"text": prompt}]
        for image in frames:
            parts.append(
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image,
                    }
                }
            )
        return {"contents": [{"role": "user", "parts": parts}]}

    def _build_prompt(self, result: AnalysisResult) -> str:
        local_story = result.combat_story or []
        local_frames = result.frames or []
        sampled_pose_frames = self._summarize_pose_frames(local_frames)
        local_findings = self._summarize_local_findings(local_story, local_frames)

        return (
            "You are a BJJ Biomechanics Analyst using a HYBRID analysis approach.\n\n"
            "ANALYSIS STRATEGY\n"
            "1. POSITIONS: Use geometric constraints such as hip centers, chest vectors, relative elevation and leg barriers.\n"
            "2. SUBMISSIONS: Use biomechanical reasoning such as leverage, pressure points, isolation and finishing mechanics.\n"
            "3. TRANSITIONS: Use both approaches combined.\n\n"
            "CRITICAL DIFFERENTIATION RULES\n"
            "- Mount vs Guard: ask whose legs create control.\n"
            "- RNC vs Triangle vs Guillotine:\n"
            "  RNC is from BACK and uses ARMS from behind.\n"
            "  Triangle is from GUARD and uses LEGS around neck/arm.\n"
            "  Guillotine is from FRONT and uses ARMS in a front headlock.\n"
            "- Kimura vs Armbar: Kimura attacks the SHOULDER with a figure-four grip; Armbar attacks the ELBOW with extension.\n"
            "- Sweep vs Takedown: Sweep starts from bottom/guard; Takedown starts standing.\n"
            "- Takedown and Triangle cannot be the same final decision for the same phase.\n\n"
            "OUTPUT ONLY VALID JSON:\n"
            "{\n"
            '  "sequence_summary": "short summary",\n'
            '  "detections": [\n'
            "    {\n"
            '      "category": "POSITION | SUBMISSION | TRANSITION | TAKEDOWN | SWEEP | PASS",\n'
            '      "label": "Technique Name",\n'
            '      "status": "Attempted | Secured | Completed",\n'
            '      "timestamp_seconds": 0.0,\n'
            '      "confidence": 0.90,\n'
            '      "detail": "why this technique and not the alternatives",\n'
            '      "observed_mechanics": ["cue 1", "cue 2"],\n'
            '      "potential_techniques": ["alt 1", "alt 2"]\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Return the best FINAL detections for the sequence. Be conservative. If unsure, prefer the simpler or more fundamental technique.\n\n"
            "TACTICAL VISION DATA (local pose extraction):\n"
            f"{sampled_pose_frames if sampled_pose_frames else '- no pose frames summary available'}\n\n"
            "LOCAL HYBRID DETECTOR FINDINGS (use as strong hints, not truth):\n"
            f"{local_findings if local_findings else '- no local findings'}\n"
        )

    async def _call_gemini(self, payload: dict[str, Any]) -> dict[str, Any]:
        model = MODEL_ALIASES.get(self.settings.gemini_model.strip(), self.settings.gemini_model.strip())
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        logger.info("Calling Gemini enrichment model=%s", model)
        async with httpx.AsyncClient(timeout=self.settings.gemini_timeout_seconds) as client:
            response = await client.post(
                url,
                params={"key": self.settings.gemini_api_key},
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    def _parse_detections(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        candidates = response.get("candidates", [])
        if not candidates:
            return []
        text_parts: list[str] = []
        for part in candidates[0].get("content", {}).get("parts", []):
            text = part.get("text")
            if text:
                text_parts.append(text)
        raw = "\n".join(text_parts).strip()
        if not raw:
            return []

        json_text = raw
        code_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
        if code_match:
            json_text = code_match.group(1)

        parsed = json.loads(json_text)
        return parsed.get("detections", [])

    def _replace_summary_with_gemini(self, result: AnalysisResult, detections: list[dict[str, Any]]) -> AnalysisResult:
        frames = list(result.frames or [])
        blocks = self._build_story_blocks(detections)
        if not blocks:
            return result

        selected = self._select_top_blocks(blocks)
        if not selected:
            return result

        for block in selected:
            self._enrich_matching_frames(
                frames,
                str(block["category"]).upper(),
                self._normalize_label(str(block["technique"])),
                block,
            )

        result.frames = frames
        result.combat_story = selected
        best_block = max(
            selected,
            key=lambda item: (
                {"POSITION": 1, "TRANSITION": 2, "SUBMISSION": 3}.get(str(item.get("category", "")).upper(), 0) * 1000
                + int(item.get("confidence", 0))
            ),
        )
        result.primary_detected_class = str(best_block.get("technique") or result.primary_detected_class)
        return result

    def _build_story_blocks(self, detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        for detection in detections:
            category = self._normalize_category(str(detection.get("category", "POSITION")))
            label = self._normalize_label(str(detection.get("label", "")))
            if not label:
                continue
            confidence = float(detection.get("confidence", 0.0) or 0.0)
            timestamp = float(detection.get("timestamp_seconds", 0.0) or 0.0)
            detail = str(detection.get("detail", "") or "").strip()
            visuals = [str(item).strip() for item in detection.get("observed_mechanics", []) if str(item).strip()]
            details = get_detection_details(category, label)
            blocks.append(
                {
                    "category": category,
                    "technique": label,
                    "label": humanize_label(label),
                    "status": str(detection.get("status", "") or self._default_status(category)).strip(),
                    "description": detail or str(details["description"]),
                    "visuals": visuals or list(details["visuals"]),
                    "confidence": int(round(confidence * 100)),
                    "start_timestamp": round(timestamp, 1),
                    "duration": 1.0,
                    "potential_techniques": [
                        self._normalize_label(str(item))
                        for item in detection.get("potential_techniques", [])
                        if str(item).strip()
                    ],
                }
            )
        return blocks

    def _select_top_blocks(self, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for block in blocks:
            grouped[str(block["category"]).upper()].append(block)

        selected: list[dict[str, Any]] = []
        chosen_position = None
        for category in ("POSITION", "SUBMISSION", "TRANSITION"):
            candidates = grouped.get(category, [])
            if not candidates:
                continue
            best = max(candidates, key=lambda item: self._score_block(item, chosen_position))
            if category == "POSITION":
                chosen_position = self._normalize_label(str(best.get("technique", "")))
            selected.append(best)

        if not any(str(item["category"]).upper() == "POSITION" for item in selected):
            inferred = self._infer_position_from_selected(selected)
            if inferred:
                selected.insert(0, inferred)
        return selected

    def _score_block(self, block: dict[str, Any], chosen_position: str | None) -> float:
        category = str(block.get("category", "")).upper()
        technique = self._normalize_label(str(block.get("technique", "")))
        confidence = int(block.get("confidence", 0))
        score = float(confidence)

        if category == "SUBMISSION":
            if technique in {"triangle", "triangle_choke", "kimura", "guillotine"}:
                score += 10.0
            if chosen_position:
                if technique in {"rear_naked_choke"} and "back" not in chosen_position:
                    score -= 40.0
                if technique in {"triangle", "triangle_choke"} and "guard" in chosen_position:
                    score += 18.0
                if technique == "guillotine" and ("guard" in chosen_position or "standing" in chosen_position or "turtle" in chosen_position):
                    score += 16.0
                if technique == "kimura" and any(token in chosen_position for token in ("side_control", "guard", "half_guard")):
                    score += 16.0
                if technique == "armbar" and technique not in {"armbar_from_mount"}:
                    score -= 4.0
        elif category == "TRANSITION":
            if technique == "takedown" and chosen_position and "standing" not in chosen_position:
                score -= 20.0
            if "guard_pass" in technique:
                score += 6.0
        return score

    def _infer_position_from_selected(self, blocks: list[dict[str, Any]]) -> dict[str, Any] | None:
        for block in blocks:
            technique = self._normalize_label(str(block.get("technique", "")))
            if technique == "kimura":
                inferred = "side_control"
            elif technique in {"triangle", "triangle_choke", "guillotine"}:
                inferred = "closed_guard"
            elif technique == "rear_naked_choke":
                inferred = "back"
            elif technique == "armbar_from_mount":
                inferred = "mount"
            else:
                continue
            details = get_detection_details("POSITION", inferred)
            return {
                "category": "POSITION",
                "technique": inferred,
                "label": humanize_label(inferred),
                "status": "Secured",
                "description": f"Positional context inferred for {humanize_label(inferred)} based on the dominant attacking mechanics in the sequence.",
                "visuals": details["visuals"],
                "confidence": 70,
                "start_timestamp": float(block.get("start_timestamp", 0.0) or 0.0),
                "duration": 1.0,
            }
        return None

    def _filter_biomechanical_hallucinations(self, detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        filtered = list(detections)
        has_takedown = any(self._normalize_category(str(item.get("category", ""))) == "TRANSITION" and "takedown" in self._normalize_label(str(item.get("label", ""))) for item in filtered)
        if has_takedown:
            filtered = [
                item for item in filtered
                if "triangle" not in self._normalize_label(str(item.get("label", "")))
            ]

        has_armbar_mount = any(
            "armbar" in self._normalize_label(str(item.get("label", "")))
            and "mount" in str(item.get("detail", "")).lower()
            for item in filtered
        )
        if has_armbar_mount:
            filtered = [
                item for item in filtered
                if "triangle" not in self._normalize_label(str(item.get("label", "")))
            ]
        return filtered

    def _filter_by_local_support(self, result: AnalysisResult, detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        local_support = self._collect_local_support(result)
        filtered: list[dict[str, Any]] = []
        for detection in detections:
            category = self._normalize_category(str(detection.get("category", "POSITION")))
            label = self._normalize_label(str(detection.get("label", "")))
            if not label:
                continue
            supported_labels = local_support.get(category, set())
            if label in supported_labels:
                filtered.append(detection)
                continue
            if any(candidate in supported_labels for candidate in self._normalized_candidates(detection)):
                filtered.append(detection)
                continue
            logger.info("Dropping Gemini detection without local support category=%s label=%s", category, label)
        return filtered

    def _collect_local_support(self, result: AnalysisResult) -> dict[str, set[str]]:
        support: dict[str, set[str]] = {"POSITION": set(), "SUBMISSION": set(), "TRANSITION": set()}
        for block in result.combat_story or []:
            category = self._normalize_category(str(block.get("category", "POSITION")))
            label = self._normalize_label(str(block.get("technique", "")))
            if label:
                support.setdefault(category, set()).add(label)
        for frame in result.frames or []:
            category = self._normalize_category(self._categorize_frame(getattr(frame, "detected_class", "")))
            label = self._normalize_label(getattr(frame, "detected_class", ""))
            if label:
                support.setdefault(category, set()).add(label)
        return support

    def _normalized_candidates(self, detection: dict[str, Any]) -> set[str]:
        candidates = {self._normalize_label(str(detection.get("label", "")))}
        for item in detection.get("potential_techniques", []) or []:
            normalized = self._normalize_label(str(item))
            if normalized:
                candidates.add(normalized)
        return candidates

    @staticmethod
    def _categorize_frame(label: str) -> str:
        lowered = str(label or "").lower()
        if any(token in lowered for token in ("armbar", "kimura", "triangle", "choke", "guillotine", "lock", "americana")):
            return "SUBMISSION"
        if any(token in lowered for token in ("pass", "sweep", "reversal", "takedown", "transition", "entry")):
            return "TRANSITION"
        return "POSITION"

    def _summarize_pose_frames(self, frames: list[Any]) -> str:
        if not frames:
            return ""
        sample_rate = max(1, len(frames) // 10)
        lines: list[str] = []
        for idx in range(0, len(frames), sample_rate):
            frame = frames[idx]
            lines.append(
                f"- Frame {getattr(frame, 'frame_index', idx)} ({getattr(frame, 'timestamp_seconds', 0.0):.1f}s): "
                f"detected_class={getattr(frame, 'detected_class', 'unknown')} confidence={getattr(frame, 'confidence', 0.0):.2f}"
            )
        return "\n".join(lines)

    def _summarize_local_findings(self, story: list[dict[str, Any]], frames: list[Any]) -> str:
        lines: list[str] = []
        seen: set[tuple[str, str]] = set()
        for block in story:
            category = str(block.get("category", "")).upper()
            technique = self._normalize_label(str(block.get("technique", "")))
            if not category or not technique:
                continue
            key = (category, technique)
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                f"- {category} ({float(block.get('start_timestamp', 0.0) or 0.0):.1f}s): {technique} "
                f"(Conf: {int(block.get('confidence', 0))}%) - {str(block.get('description', '')).strip()}"
            )
        for frame in frames[:12]:
            technique = self._normalize_label(getattr(frame, "detected_class", ""))
            if not technique:
                continue
            key = ("FRAME", technique)
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                f"- FRAME ({getattr(frame, 'timestamp_seconds', 0.0):.1f}s): {technique} "
                f"(Conf: {int(round(getattr(frame, 'confidence', 0.0) * 100))}%)"
            )
        return "\n".join(lines)

    def _enrich_matching_frames(
        self,
        frames: list[Any],
        category: str,
        local_label: str,
        detection: dict[str, Any],
    ) -> None:
        for frame in frames:
            frame_label = self._normalize_label(getattr(frame, "detected_class", ""))
            if category == "SUBMISSION" and frame_label == local_label:
                frame.feedback = detection["description"]
            elif category == "POSITION" and frame_label == local_label:
                frame.feedback = detection["description"]
            elif category == "TRANSITION" and frame_label == local_label:
                frame.feedback = detection["description"]

    @staticmethod
    def _normalize_category(category: str) -> str:
        normalized = category.strip().upper()
        if normalized in {"TAKEDOWN", "SWEEP", "PASS"}:
            return "TRANSITION"
        if normalized not in {"POSITION", "SUBMISSION", "TRANSITION"}:
            return "POSITION"
        return normalized

    @staticmethod
    def _normalize_label(label: str) -> str:
        return label.strip().lower().replace(" ", "_")

    @staticmethod
    def _default_status(category: str) -> str:
        if category == "SUBMISSION":
            return "Attempted"
        if category == "TRANSITION":
            return "Completed"
        return "Secured"
