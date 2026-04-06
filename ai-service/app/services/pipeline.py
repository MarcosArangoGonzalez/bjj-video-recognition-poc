from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from statistics import mean
from typing import Any, Optional

from app.config import Settings
from app.core.logging import get_logger
from app.schemas.analysis import AnalysisRequest, AnalysisResult, DetectedFrameDto
from app.services.knowledge_descriptions import get_detection_details, humanize_label
from app.services.python_sidecar import PythonSidecarClient
from app.services.spring_poc_client import SpringPocClient

logger = get_logger(__name__)

NOISE_LABELS = {"scramble", "technique_unknown", "standing", "unknown", "ground_position", "no_data"}
MIN_POSITION_CONFIDENCE = 0.50
TECHNICAL_POSITION_THRESHOLD = 0.60
NOISE_POSITION_PENALTIES = {"standing": 0.18, "scramble": 0.22}
MIN_TECHNIQUE_CONFIDENCE = 0.65
DOUBLE_THREAT_CONFIDENCE = 0.85
TIME_BLOCK_SECONDS = 2.0
DOUBLE_THREAT_PAIRS = {frozenset({"triangle_choke", "armbar"})}
STORY_HIERARCHY = {"SUBMISSION": 3, "TRANSITION": 2, "POSITION": 1}
VERDICT_CATEGORY_ORDER = ("POSITION", "SUBMISSION", "TRANSITION")
POSITION_ALIASES = {
    "mount1": "mount",
    "mount2": "mount",
    "back1": "back",
    "back2": "back",
    "back_control": "back",
    "side_control1": "side_control",
    "side_control2": "side_control",
    "closed_guard1": "closed_guard",
    "closed_guard2": "closed_guard",
    "open_guard1": "open_guard",
    "open_guard2": "open_guard",
    "half_guard1": "half_guard",
    "half_guard2": "half_guard",
    "turtle1": "turtle",
    "turtle2": "turtle",
    "5050_guard": "50/50_guard",
}
SUBMISSION_POSITION_CONTEXT = {
    "kimura": {"side_control", "north_south", "closed_guard", "half_guard"},
    "armbar": {"mount", "closed_guard", "open_guard", "side_control", "back"},
    "armbar_from_mount": {"mount"},
    "triangle_choke": {"closed_guard", "open_guard", "half_guard", "50/50_guard"},
    "guillotine": {"closed_guard", "open_guard", "half_guard", "turtle", "standing"},
    "rear_naked_choke": {"back"},
    "americana": {"side_control", "mount"},
}
TRANSITION_POSITION_CONTEXT = {
    "guard_pass_to_side_control": {"closed_guard", "open_guard", "half_guard", "side_control"},
    "guard_pass_to_mount": {"closed_guard", "open_guard", "half_guard", "mount"},
    "guard_pass": {"closed_guard", "open_guard", "half_guard", "side_control", "mount"},
    "takedown": {"standing"},
    "takedown_entry": {"standing"},
    "sweep": {"closed_guard", "open_guard", "half_guard", "50/50_guard", "turtle"},
    "reversal": {"closed_guard", "open_guard", "half_guard", "turtle"},
}
INFERRED_POSITION_BY_SUBMISSION = {
    "kimura": "side_control",
    "armbar_from_mount": "mount",
    "triangle_choke": "closed_guard",
    "guillotine": "closed_guard",
    "rear_naked_choke": "back",
}
TECHNIQUE_PRIORS = {
    "kimura": 14.0,
    "triangle_choke": 14.0,
    "guillotine": 14.0,
    "armbar_from_mount": 12.0,
    "rear_naked_choke": 10.0,
    "americana": 8.0,
    "armbar": 2.0,
}
POSITION_MIN_SCORE = 48.0
TECHNIQUE_MIN_SCORE = 54.0


@dataclass(slots=True)
class FrameContext:
    frame_index: int
    timestamp_seconds: float
    detected_class: str
    confidence: float
    joint_angles: Optional[dict]
    suggested_tags: list[dict] | None
    player_role: str | None = None
    feedback: str | None = None


class VideoAnalysisPipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.sidecar = PythonSidecarClient(settings)
        self.spring_poc = SpringPocClient(settings)

    def analyze(self, publication_id: int, request: AnalysisRequest, video_source: str) -> AnalysisResult:
        if self.settings.spring_poc_enabled:
            return self._analyze_with_spring_poc(publication_id, request, video_source)

        raw_frames = self._analyze_video_with_python_service(video_source)
        if not raw_frames:
            raise RuntimeError("No analyzable frames were produced from the video")

        if self.settings.python_parity_mode:
            frames = self._build_detected_frames(raw_frames, request)
            combat_story = self._select_verdict_story(raw_frames)
        else:
            self._stabilize_positions(raw_frames)
            frames = self._build_detected_frames(raw_frames, request)
            self._apply_detected_class_hysteresis(frames, request.auto_tag)
            combat_story = self._build_final_story(raw_frames)
        primary_detected_class = self._compute_primary_class(combat_story, frames)

        return AnalysisResult(
            publication_id=publication_id,
            status="completed",
            frames=frames,
            combat_story=combat_story,
            primary_detected_class=primary_detected_class,
        )

    @classmethod
    def _parse_spring_tag(cls, tag: dict[str, Any]) -> dict[str, Any] | None:
        raw_name = str(tag.get("tagName", "")).strip()
        if not raw_name:
            return None
        match = re.match(r"^(?P<category>[A-Z_ ]+):\s*(?P<label>.+?)(?:\s+\((?P<status>[^)]+)\))?(?::\s*(?P<body>.*))?$", raw_name)
        if not match:
            return None

        category = cls._normalize_category(match.group("category"))
        label = (match.group("label") or "").strip()
        status = (match.group("status") or cls._default_status(category, float(tag.get("confidence", 0.0) or 0.0))).strip()
        body = (match.group("body") or "").strip()
        description = body
        visuals: list[str] = []
        visuals_match = re.search(r"\[Visuals:\s*(.*?)\]\s*$", body)
        if visuals_match:
            visuals_text = visuals_match.group(1).strip()
            visuals = [item.strip() for item in visuals_text.split(",") if item.strip()]
            description = body[:visuals_match.start()].strip()

        confidence = int(round(float(tag.get("confidence", 0.0) or 0.0) * 100))
        timestamp = round(float(tag.get("timestampSeconds", 0.0) or 0.0), 1)
        technique = cls._normalize_position_label(cls._canonicalize_label(label))
        return {
            "category": category,
            "technique": technique,
            "label": label,
            "status": status,
            "description": description,
            "visuals": visuals,
            "confidence": confidence,
            "start_timestamp": timestamp,
            "duration": 1.0,
        }

    @classmethod
    def _spring_tag_to_frame(cls, tag: dict[str, Any], request: AnalysisRequest) -> DetectedFrameDto | None:
        block = cls._parse_spring_tag(tag)
        if block is None:
            return None
        confidence = float(tag.get("confidence", 0.0) or 0.0)
        detected_class = str(block["technique"] or "scramble")
        return DetectedFrameDto(
            frame_index=int(round(float(tag.get("timestampSeconds", 0.0) or 0.0) * 2)),
            timestamp_seconds=float(tag.get("timestampSeconds", 0.0) or 0.0),
            detected_class=detected_class,
            confidence=confidence,
            joint_angles=None,
            feedback=str(block.get("description") or ""),
            suggested_tags=cls._suggested_tags(request.auto_tag, detected_class, confidence),
            player_role=cls._infer_player_role(detected_class),
        )

    @staticmethod
    def _canonicalize_label(label: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", str(label or "").strip().lower()).strip("_")
        aliases = {
            "rear_naked_choke": "rear_naked_choke",
            "triangle_choke": "triangle_choke",
            "triangle": "triangle_choke",
            "guillotine_choke": "guillotine",
            "guillotine": "guillotine",
            "side_control": "side_control",
            "closed_guard": "closed_guard",
            "open_guard": "open_guard",
            "half_guard": "half_guard",
            "back_control": "back",
            "guard": "closed_guard",
        }
        return aliases.get(normalized, normalized)

    def _analyze_with_spring_poc(self, publication_id: int, request: AnalysisRequest, video_source: str) -> AnalysisResult:
        video_dto = self.spring_poc.analyze_video(video_source)
        tags = list(video_dto.get("tags", []) or [])
        combat_story = [block for block in (self._parse_spring_tag(tag) for tag in tags) if block is not None]
        frames = [frame for frame in (self._spring_tag_to_frame(tag, request) for tag in tags) if frame is not None]
        primary_detected_class = self._compute_primary_class(combat_story, frames)
        return AnalysisResult(
            publication_id=publication_id,
            status="completed",
            frames=frames,
            combat_story=combat_story,
            primary_detected_class=primary_detected_class,
        )

    def _analyze_video_with_python_service(self, video_source: str) -> list[dict[str, Any]]:
        response = self.sidecar.analyze_video(video_source, self.settings.analysis_fps)
        raw_frames = list(response.get("frames", []) or [])
        for frame in raw_frames:
            if "sourceFrameIndex" not in frame:
                frame["sourceFrameIndex"] = int(frame.get("frameNumber", 0))
            self._debug_frame_decision(frame)
        return raw_frames

    @classmethod
    def _build_final_story(cls, raw_frames: list[dict[str, Any]] | list[DetectedFrameDto]) -> list[dict]:
        if raw_frames and isinstance(raw_frames[0], DetectedFrameDto):
            iterable = []
            for frame in raw_frames:
                iterable.append(
                    {
                        "timestampSeconds": frame.timestamp_seconds,
                        "predictedPosition": frame.detected_class if cls._categorize(frame.detected_class) == "POSITION" else None,
                        "positionConfidence": frame.confidence if cls._categorize(frame.detected_class) == "POSITION" else 0.0,
                        "allTechniques": [
                            {
                                "type": cls._categorize(frame.detected_class).lower(),
                                "name": frame.detected_class,
                                "confidence": frame.confidence,
                            }
                        ] if cls._categorize(frame.detected_class) != "POSITION" else [],
                    }
                )
        else:
            iterable = raw_frames

        return cls._build_unique_story(iterable)

    def _stabilize_positions(self, frames: list[dict[str, Any]]) -> None:
        pos_scores: dict[str, dict[str, float]] = {}
        for frame in frames:
            position = self._normalize_position_label(frame.get("predictedPosition"))
            confidence = float(frame.get("positionConfidence", 0.0) or 0.0)
            if not position or position in NOISE_LABELS or confidence < MIN_POSITION_CONFIDENCE:
                continue
            stats = pos_scores.setdefault(position, {"count": 0.0, "total_conf": 0.0, "weighted_conf": 0.0})
            stats["count"] += 1
            stats["total_conf"] += confidence
            stats["weighted_conf"] += max(confidence - NOISE_POSITION_PENALTIES.get(position, 0.0), 0.0)

        if not pos_scores:
            return

        technical_candidates = {
            label: stats
            for label, stats in pos_scores.items()
            if label not in {"standing", "scramble"}
            and (stats["total_conf"] / max(stats["count"], 1.0)) >= TECHNICAL_POSITION_THRESHOLD
        }
        candidate_pool = technical_candidates or pos_scores
        best_position = max(candidate_pool.items(), key=lambda item: item[1]["weighted_conf"])[0]
        avg_conf = pos_scores[best_position]["total_conf"] / pos_scores[best_position]["count"]
        logger.info("Stabilizing video position to=%s avg_conf=%.2f", best_position, avg_conf)

        for frame in frames:
            frame["predictedPosition"] = best_position
            frame["positionConfidence"] = avg_conf
            if "allTechniques" in frame:
                filtered = []
                for technique in frame["allTechniques"]:
                    if str(technique.get("type", "")).upper() == "POSITION":
                        if self._normalize_position_label(technique.get("name")) == best_position:
                            filtered.append(
                                {
                                    **technique,
                                    "name": best_position,
                                    "confidence": avg_conf,
                                }
                            )
                    else:
                        filtered.append(technique)
                if not any(
                    str(item.get("type", "")).upper() == "POSITION"
                    and self._normalize_position_label(item.get("name")) == best_position
                    for item in filtered
                ):
                    filtered.append(
                        {
                            "type": "position",
                            "name": best_position,
                            "confidence": avg_conf,
                            "source": "majority_vote",
                            "reasoning": "Stabilized by majority vote",
                        }
                    )
                frame["allTechniques"] = filtered

    def _build_detected_frames(self, raw_frames: list[dict[str, Any]], request: AnalysisRequest) -> list[DetectedFrameDto]:
        frames: list[DetectedFrameDto] = []
        for frame in raw_frames:
            detected_class, confidence = self._select_primary_detection(frame)
            details = get_detection_details(self._categorize(detected_class), detected_class)
            frames.append(
                DetectedFrameDto(
                    frame_index=int(frame.get("sourceFrameIndex", frame.get("frameNumber", 0))),
                    timestamp_seconds=float(frame.get("timestampSeconds", 0.0) or 0.0),
                    detected_class=detected_class,
                    confidence=confidence,
                    joint_angles=frame.get("joint_angles") if request.biometric_tracking else None,
                    feedback=str(details["description"]),
                    suggested_tags=self._suggested_tags(request.auto_tag, detected_class, confidence),
                    player_role=self._infer_player_role(detected_class),
                )
            )
        return frames

    def _apply_detected_class_hysteresis(self, frames: list[DetectedFrameDto], auto_tag: bool) -> None:
        stable_label: str | None = None
        candidate_label: str | None = None
        candidate_count = 0

        for frame in frames:
            current = frame.detected_class
            if stable_label is None:
                stable_label = current
                continue

            if current == stable_label:
                candidate_label = None
                candidate_count = 0
                continue

            if current == candidate_label:
                candidate_count += 1
            else:
                candidate_label = current
                candidate_count = 1

            if candidate_count >= 15:
                stable_label = candidate_label
                candidate_label = None
                candidate_count = 0
            else:
                frame.detected_class = stable_label
                details = get_detection_details(self._categorize(stable_label), stable_label)
                frame.feedback = str(details["description"])
                frame.suggested_tags = self._suggested_tags(auto_tag, stable_label, frame.confidence)

    @classmethod
    def _build_unique_story(cls, raw_frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
        story: list[dict[str, Any]] = []
        for block in cls._group_time_blocks(raw_frames):
            story.extend(cls._build_block_story(block))
        story.sort(key=lambda item: (item["start_timestamp"], -STORY_HIERARCHY.get(item["category"], 0), -item["confidence"]))
        return story

    @classmethod
    def _group_time_blocks(cls, raw_frames: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        blocks: dict[int, list[dict[str, Any]]] = {}
        for frame in raw_frames:
            timestamp = float(frame.get("timestampSeconds", 0.0) or 0.0)
            block_index = int(timestamp // TIME_BLOCK_SECONDS)
            blocks.setdefault(block_index, []).append(frame)
        return [blocks[index] for index in sorted(blocks)]

    @classmethod
    def _build_block_story(cls, block_frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not block_frames:
            return []

        block_story: list[dict[str, Any]] = []
        start_timestamp = round(float(block_frames[0].get("timestampSeconds", 0.0) or 0.0), 1)
        duration = max(
            1.0,
            round(float(block_frames[-1].get("timestampSeconds", start_timestamp) or start_timestamp) - start_timestamp + 1.0, 1),
        )
        positions: dict[str, dict[str, Any]] = {}
        submissions: dict[str, dict[str, Any]] = {}
        transitions: dict[str, dict[str, Any]] = {}

        for frame in block_frames:
            timestamp = float(frame.get("timestampSeconds", 0.0) or 0.0)
            position = cls._normalize_position_label(frame.get("predictedPosition"))
            position_conf = float(frame.get("positionConfidence", 0.0) or 0.0)
            if position and position not in NOISE_LABELS and position_conf >= MIN_POSITION_CONFIDENCE:
                entry = positions.setdefault(position, {"sum_conf": 0.0, "max_conf": 0.0, "first_timestamp": timestamp})
                entry["sum_conf"] += position_conf
                entry["max_conf"] = max(entry["max_conf"], position_conf)
                entry["first_timestamp"] = min(entry["first_timestamp"], timestamp)

            for technique in frame.get("allTechniques", []) or []:
                category = cls._normalize_category(str(technique.get("type", "")))
                if category == "POSITION":
                    continue
                label = cls._normalize_position_label(technique.get("name"))
                confidence = float(technique.get("confidence", 0.0) or 0.0)
                if not label or confidence < MIN_TECHNIQUE_CONFIDENCE:
                    continue
                target = submissions if category == "SUBMISSION" else transitions
                entry = target.setdefault(label, {"sum_conf": 0.0, "max_conf": 0.0, "first_timestamp": timestamp})
                entry["sum_conf"] += confidence
                entry["max_conf"] = max(entry["max_conf"], confidence)
                entry["first_timestamp"] = min(entry["first_timestamp"], timestamp)

        if "triangle_choke" in submissions:
            submissions.pop("guillotine", None)
            submissions.pop("kimura", None)

        if positions:
            best_position, stats = max(positions.items(), key=lambda item: item[1]["sum_conf"])
            details = get_detection_details("POSITION", best_position)
            block_story.append(
                {
                    "category": "POSITION",
                    "technique": best_position,
                    "label": humanize_label(best_position),
                    "status": "Secured",
                    "description": details["description"],
                    "visuals": details["visuals"],
                    "confidence": int(round(stats["max_conf"] * 100)),
                    "start_timestamp": round(stats["first_timestamp"], 1),
                    "duration": duration,
                }
            )

        if submissions:
            ranked = sorted(submissions.items(), key=lambda item: (item[1]["sum_conf"], item[1]["max_conf"]), reverse=True)
            winners = [ranked[0]]
            if len(ranked) > 1:
                first_label, first_stats = ranked[0]
                second_label, second_stats = ranked[1]
                if (
                    first_stats["max_conf"] >= DOUBLE_THREAT_CONFIDENCE
                    and second_stats["max_conf"] >= DOUBLE_THREAT_CONFIDENCE
                    and frozenset({first_label, second_label}) in DOUBLE_THREAT_PAIRS
                ):
                    winners.append(ranked[1])
            for label, stats in winners:
                details = get_detection_details("SUBMISSION", label)
                block_story.append(
                    {
                        "category": "SUBMISSION",
                        "technique": label,
                        "label": humanize_label(label),
                        "status": cls._default_status("SUBMISSION", stats["max_conf"]),
                        "description": details["description"],
                        "visuals": details["visuals"],
                        "confidence": int(round(stats["max_conf"] * 100)),
                        "start_timestamp": round(stats["first_timestamp"], 1),
                        "duration": duration,
                    }
                )

        if transitions:
            best_transition, stats = max(transitions.items(), key=lambda item: (item[1]["sum_conf"], item[1]["max_conf"]))
            details = get_detection_details("TRANSITION", best_transition)
            block_story.append(
                {
                    "category": "TRANSITION",
                    "technique": best_transition,
                    "label": humanize_label(best_transition),
                    "status": cls._default_status("TRANSITION", stats["max_conf"]),
                    "description": details["description"],
                    "visuals": details["visuals"],
                    "confidence": int(round(stats["max_conf"] * 100)),
                    "start_timestamp": round(stats["first_timestamp"], 1),
                    "duration": duration,
                }
            )

        return block_story

    @classmethod
    def _select_verdict_story(cls, raw_frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not raw_frames:
            return []

        position_stats = cls._aggregate_position_stats(raw_frames)
        technique_stats = cls._aggregate_technique_stats(raw_frames)

        selected_submission = cls._pick_best_candidate("SUBMISSION", technique_stats.get("SUBMISSION", {}), position_stats)
        selected_transition = cls._pick_best_candidate("TRANSITION", technique_stats.get("TRANSITION", {}), position_stats)
        selected_position = cls._pick_best_position(position_stats, selected_submission, selected_transition)

        story: list[dict[str, Any]] = []
        if selected_position:
            story.append(cls._build_story_block("POSITION", selected_position["technique"], selected_position))
        if selected_submission:
            story.append(cls._build_story_block("SUBMISSION", selected_submission["technique"], selected_submission))
        if selected_transition:
            story.append(cls._build_story_block("TRANSITION", selected_transition["technique"], selected_transition))

        story.sort(
            key=lambda item: (
                VERDICT_CATEGORY_ORDER.index(item["category"]) if item["category"] in VERDICT_CATEGORY_ORDER else 99,
                item["start_timestamp"],
            )
        )
        return story

    @classmethod
    def _aggregate_position_stats(cls, raw_frames: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        stats: dict[str, dict[str, Any]] = {}
        timestamps = [float(frame.get("timestampSeconds", 0.0) or 0.0) for frame in raw_frames]
        total_duration = max(timestamps) if timestamps else 0.0
        timeline: list[str] = []

        for frame in raw_frames:
            position = cls._normalize_position_label(frame.get("predictedPosition"))
            confidence = float(frame.get("positionConfidence", 0.0) or 0.0)
            timestamp = float(frame.get("timestampSeconds", 0.0) or 0.0)
            if not position or position in NOISE_LABELS or confidence <= 0.0:
                timeline.append("")
                continue
            timeline.append(position)
            entry = stats.setdefault(
                position,
                {"count": 0, "confidences": [], "timestamps": [], "first_timestamp": timestamp, "last_timestamp": timestamp},
            )
            entry["count"] += 1
            entry["confidences"].append(confidence)
            entry["timestamps"].append(timestamp)
            entry["first_timestamp"] = min(entry["first_timestamp"], timestamp)
            entry["last_timestamp"] = max(entry["last_timestamp"], timestamp)

        for label, entry in stats.items():
            entry["longest_streak"] = cls._compute_longest_streak(timeline, label)
            entry["avg_conf"] = mean(entry["confidences"])
            entry["max_conf"] = max(entry["confidences"])
            entry["recency"] = (entry["last_timestamp"] / total_duration) if total_duration > 0 else 0.0
            entry["score"] = (
                entry["count"] * 14.0
                + entry["avg_conf"] * 55.0
                + entry["max_conf"] * 20.0
                + entry["longest_streak"] * 8.0
            )
        return stats

    @classmethod
    def _aggregate_technique_stats(cls, raw_frames: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
        stats: dict[str, dict[str, dict[str, Any]]] = {"SUBMISSION": {}, "TRANSITION": {}}
        timestamps = [float(frame.get("timestampSeconds", 0.0) or 0.0) for frame in raw_frames]
        total_duration = max(timestamps) if timestamps else 0.0
        timeline_by_category: dict[str, list[str]] = {"SUBMISSION": [], "TRANSITION": []}

        for frame in raw_frames:
            techniques = list(frame.get("allTechniques", []) or [])
            timestamp = float(frame.get("timestampSeconds", 0.0) or 0.0)
            best_by_category: dict[str, tuple[str, float]] = {}
            for technique in techniques:
                category = cls._normalize_category(str(technique.get("type", "")))
                if category not in {"SUBMISSION", "TRANSITION"}:
                    continue
                label = cls._normalize_position_label(technique.get("name"))
                confidence = float(technique.get("confidence", 0.0) or 0.0)
                if not label or confidence <= 0.0:
                    continue
                current = best_by_category.get(category)
                if current is None or confidence > current[1]:
                    best_by_category[category] = (label, confidence)

            for category in timeline_by_category:
                timeline_by_category[category].append(best_by_category.get(category, ("", 0.0))[0])

            for category, (label, confidence) in best_by_category.items():
                entry = stats[category].setdefault(
                    label,
                    {"count": 0, "confidences": [], "timestamps": [], "first_timestamp": timestamp, "last_timestamp": timestamp},
                )
                entry["count"] += 1
                entry["confidences"].append(confidence)
                entry["timestamps"].append(timestamp)
                entry["first_timestamp"] = min(entry["first_timestamp"], timestamp)
                entry["last_timestamp"] = max(entry["last_timestamp"], timestamp)

        for category, labels in stats.items():
            for label, entry in labels.items():
                entry["longest_streak"] = cls._compute_longest_streak(timeline_by_category[category], label)
                entry["avg_conf"] = mean(entry["confidences"])
                entry["max_conf"] = max(entry["confidences"])
                entry["recency"] = (entry["last_timestamp"] / total_duration) if total_duration > 0 else 0.0
        return stats

    @classmethod
    def _pick_best_candidate(
        cls,
        category: str,
        candidates: dict[str, dict[str, Any]],
        position_stats: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        best: dict[str, Any] | None = None
        for label, entry in candidates.items():
            compatible_positions = (
                SUBMISSION_POSITION_CONTEXT.get(label, set())
                if category == "SUBMISSION"
                else TRANSITION_POSITION_CONTEXT.get(label, set())
            )
            support_score = 0.0
            support_position = None
            if compatible_positions:
                for position in compatible_positions:
                    stats = position_stats.get(position)
                    if not stats:
                        continue
                    candidate_score = stats["count"] * 8.0 + stats["avg_conf"] * 25.0 + stats["longest_streak"] * 5.0
                    if candidate_score > support_score:
                        support_score = candidate_score
                        support_position = position

            score = (
                entry["count"] * 18.0
                + entry["avg_conf"] * 55.0
                + entry["max_conf"] * 18.0
                + entry["longest_streak"] * 9.0
                + entry["recency"] * 10.0
                + support_score
                + TECHNIQUE_PRIORS.get(label, 0.0)
            )
            if compatible_positions and support_score <= 0.0:
                score -= 35.0

            enriched = {**entry, "technique": label, "score": score}
            if support_position:
                enriched["supported_position"] = support_position
            if best is None or score > best["score"]:
                best = enriched

        threshold = TECHNIQUE_MIN_SCORE if category in {"SUBMISSION", "TRANSITION"} else POSITION_MIN_SCORE
        if best and best["score"] >= threshold:
            return best
        return None

    @classmethod
    def _pick_best_position(
        cls,
        position_stats: dict[str, dict[str, Any]],
        selected_submission: dict[str, Any] | None,
        selected_transition: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        best: dict[str, Any] | None = None
        for label, entry in position_stats.items():
            score = float(entry["score"])
            if selected_submission:
                compatible = SUBMISSION_POSITION_CONTEXT.get(selected_submission["technique"], set())
                if label in compatible:
                    score += 26.0
                elif compatible:
                    score -= 18.0
            if selected_transition:
                compatible = TRANSITION_POSITION_CONTEXT.get(selected_transition["technique"], set())
                if label in compatible:
                    score += 12.0
            enriched = {**entry, "technique": label, "score": score}
            if best is None or score > best["score"]:
                best = enriched

        if best and best["score"] >= POSITION_MIN_SCORE:
            return best

        if selected_submission:
            inferred = INFERRED_POSITION_BY_SUBMISSION.get(selected_submission["technique"])
            if inferred:
                support = position_stats.get(inferred)
                confidence = int(round((support["avg_conf"] if support else 0.7) * 100))
                timestamp = support["first_timestamp"] if support else selected_submission["first_timestamp"]
                return {
                    "technique": inferred,
                    "score": 70.0,
                    "avg_conf": (support["avg_conf"] if support else 0.7),
                    "max_conf": (support["max_conf"] if support else 0.7),
                    "first_timestamp": timestamp,
                    "last_timestamp": support["last_timestamp"] if support else timestamp,
                    "count": support["count"] if support else 1,
                    "longest_streak": support["longest_streak"] if support else 1,
                    "inferred": True,
                    "confidence_override": confidence,
                }
        return None

    @classmethod
    def _build_story_block(cls, category: str, technique: str, stats: dict[str, Any]) -> dict[str, Any]:
        details = get_detection_details(category, technique)
        confidence = int(round(stats.get("confidence_override", stats.get("avg_conf", 0.0) * 100)))
        status = cls._default_status(category, stats.get("max_conf", stats.get("avg_conf", 0.0)))
        description = details["description"]
        if category == "POSITION" and stats.get("inferred"):
            description = f"Positional context inferred from the dominant {humanize_label(technique).lower()} mechanics in the sequence."
        duration = max(1.0, round(float(stats.get("last_timestamp", stats.get("first_timestamp", 0.0))) - float(stats.get("first_timestamp", 0.0)) + 1.0, 1))
        return {
            "category": category,
            "technique": technique,
            "label": humanize_label(technique),
            "status": status,
            "description": description,
            "visuals": details["visuals"],
            "confidence": confidence,
            "start_timestamp": round(float(stats.get("first_timestamp", 0.0)), 1),
            "duration": duration,
        }

    @staticmethod
    def _compute_longest_streak(timeline: list[str], label: str) -> int:
        longest = 0
        current = 0
        for item in timeline:
            if item == label:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        return longest

    @classmethod
    def _compute_primary_class(cls, combat_story: list[dict], frames: list[DetectedFrameDto]) -> str:
        if combat_story:
            best = max(
                combat_story,
                key=lambda item: STORY_HIERARCHY.get(item["category"], 0) * 1000 + int(item.get("confidence", 0)),
            )
            return str(best.get("technique") or "scramble")

        counts = Counter(frame.detected_class for frame in frames if frame.detected_class not in NOISE_LABELS)
        return counts.most_common(1)[0][0] if counts else "scramble"

    @classmethod
    def _select_primary_detection(cls, frame: dict[str, Any]) -> tuple[str, float]:
        techniques = list(frame.get("allTechniques", []) or [])
        if techniques:
            filtered = [item for item in techniques if float(item.get("confidence", 0.0) or 0.0) >= MIN_TECHNIQUE_CONFIDENCE]
            if filtered:
                best = max(filtered, key=lambda item: float(item.get("confidence", 0.0) or 0.0))
                label = cls._normalize_position_label(best.get("name"))
                confidence = float(best.get("confidence", 0.0) or 0.0)
                if label and label not in NOISE_LABELS:
                    return label, confidence

        position = cls._normalize_position_label(frame.get("predictedPosition"))
        confidence = float(frame.get("positionConfidence", frame.get("confidence", 0.0)) or 0.0)
        return position or "scramble", confidence

    def _debug_frame_decision(self, result: dict[str, Any]) -> None:
        if not self.settings.debug_frame_decisions:
            return
        techniques = [
            f"{self._normalize_category(str(item.get('type', '')))}:{self._normalize_position_label(item.get('name'))}:{float(item.get('confidence', 0.0) or 0.0):.2f}"
            for item in result.get("allTechniques", []) or []
        ]
        logger.info(
            "Frame decision idx=%s t=%.2f pos=%s pos_conf=%.2f candidates=%s",
            result.get("sourceFrameIndex", result.get("frameNumber", 0)),
            float(result.get("timestampSeconds", 0.0) or 0.0),
            self._normalize_position_label(result.get("predictedPosition")),
            float(result.get("positionConfidence", 0.0) or 0.0),
            techniques[:8],
        )

    @staticmethod
    def _normalize_position_label(label: Any) -> str:
        normalized = str(label or "").strip().lower().replace(" ", "_")
        return POSITION_ALIASES.get(normalized, normalized)

    @staticmethod
    def _normalize_category(category: str) -> str:
        normalized = category.strip().upper()
        if normalized in {"SWEEP", "TAKEDOWN", "TRANSITION", "PASS"}:
            return "TRANSITION"
        if normalized == "SUBMISSION":
            return "SUBMISSION"
        return "POSITION"

    @staticmethod
    def _categorize(label: str) -> str:
        lowered = str(label or "").lower()
        if any(token in lowered for token in ("armbar", "kimura", "triangle", "choke", "guillotine", "lock")):
            return "SUBMISSION"
        if any(token in lowered for token in ("pass", "sweep", "reversal", "takedown", "transition", "entry")):
            return "TRANSITION"
        return "POSITION"

    @staticmethod
    def _default_status(category: str, confidence: float) -> str:
        if category == "SUBMISSION":
            return "Secured" if confidence >= 0.85 else "Attempted"
        if category == "TRANSITION":
            return "Completed"
        return "Secured"

    @staticmethod
    def _suggested_tags(enabled: bool, detected_class: str, confidence: float) -> list[dict] | None:
        if not enabled:
            return None
        if confidence < 0.60:
            if any(token in detected_class.lower() for token in ("armbar", "kimura", "triangle", "choke", "guillotine", "lock", "americana", "pass", "sweep", "reversal", "takedown")):
                return None
        return [{"tag": detected_class, "confidence": round(confidence, 3)}]

    @staticmethod
    def _infer_player_role(detected_class: str) -> str | None:
        label = detected_class.lower()
        if any(token in label for token in ("mount", "side_control", "back")):
            return "ATTACKER_TOP"
        if "guard" in label:
            return "ATTACKER_BOTTOM"
        return None
