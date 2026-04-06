from __future__ import annotations

from dataclasses import dataclass
from math import acos, atan2, degrees, sqrt
from typing import Optional

import numpy as np

from app.schemas.analysis import JointAngles

KEYPOINT_NAMES = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]
KP = {name: index for index, name in enumerate(KEYPOINT_NAMES)}


@dataclass(slots=True)
class TechniqueCandidate:
    type: str
    name: str
    confidence: float
    reasoning: str


def _valid_point(point: list[float]) -> bool:
    return len(point) >= 3 and point[2] >= 0.1


def _angle(a: list[float], b: list[float], c: list[float]) -> Optional[float]:
    if not (_valid_point(a) and _valid_point(b) and _valid_point(c)):
        return None
    ba = np.array([a[0] - b[0], a[1] - b[1]], dtype=float)
    bc = np.array([c[0] - b[0], c[1] - b[1]], dtype=float)
    norm_ba = np.linalg.norm(ba)
    norm_bc = np.linalg.norm(bc)
    if norm_ba < 1e-6 or norm_bc < 1e-6:
        return None
    cos_value = float(np.dot(ba, bc) / (norm_ba * norm_bc))
    return round(degrees(acos(max(-1.0, min(1.0, cos_value)))), 1)


class GeometryService:
    def compute_joint_angles(self, keypoints: list[list[float]]) -> JointAngles:
        if len(keypoints) < 17:
            return JointAngles()

        left_shoulder = keypoints[KP["left_shoulder"]]
        right_shoulder = keypoints[KP["right_shoulder"]]
        left_elbow = keypoints[KP["left_elbow"]]
        right_elbow = keypoints[KP["right_elbow"]]
        left_wrist = keypoints[KP["left_wrist"]]
        right_wrist = keypoints[KP["right_wrist"]]
        left_hip = keypoints[KP["left_hip"]]
        right_hip = keypoints[KP["right_hip"]]
        left_knee = keypoints[KP["left_knee"]]
        right_knee = keypoints[KP["right_knee"]]
        left_ankle = keypoints[KP["left_ankle"]]
        right_ankle = keypoints[KP["right_ankle"]]

        hip_mid = self._midpoint(left_hip, right_hip)
        shoulder_mid = self._midpoint(left_shoulder, right_shoulder)
        knee_mid = self._midpoint(left_knee, right_knee)

        spine_tilt_angle = None
        if _valid_point(hip_mid) and _valid_point(shoulder_mid):
            dx = shoulder_mid[0] - hip_mid[0]
            dy = shoulder_mid[1] - hip_mid[1]
            if sqrt(dx * dx + dy * dy) > 1.0:
                spine_tilt_angle = round(degrees(atan2(abs(dx), abs(dy) if abs(dy) > 1e-6 else 1e-6)), 1)

        return JointAngles(
            left_elbow_angle=_angle(left_shoulder, left_elbow, left_wrist),
            right_elbow_angle=_angle(right_shoulder, right_elbow, right_wrist),
            left_knee_angle=_angle(left_hip, left_knee, left_ankle),
            right_knee_angle=_angle(right_hip, right_knee, right_ankle),
            hip_spine_angle=_angle(shoulder_mid, hip_mid, knee_mid),
            spine_tilt_angle=spine_tilt_angle,
        )

    def detect(self, keypoints: list[list[float]], position: str | None) -> list[TechniqueCandidate]:
        if len(keypoints) < 17:
            return []

        nose = keypoints[KP["nose"]]
        left_shoulder = keypoints[KP["left_shoulder"]]
        right_shoulder = keypoints[KP["right_shoulder"]]
        left_wrist = keypoints[KP["left_wrist"]]
        right_wrist = keypoints[KP["right_wrist"]]
        left_hip = keypoints[KP["left_hip"]]
        right_hip = keypoints[KP["right_hip"]]
        left_knee = keypoints[KP["left_knee"]]
        right_knee = keypoints[KP["right_knee"]]
        left_ankle = keypoints[KP["left_ankle"]]
        right_ankle = keypoints[KP["right_ankle"]]

        hip_mid = self._midpoint(left_hip, right_hip)
        shoulder_mid = self._midpoint(left_shoulder, right_shoulder)
        body_scale = max(self._distance(hip_mid, shoulder_mid), 1.0)

        techniques: list[TechniqueCandidate] = []

        left_arm_extension = self._distance(left_wrist, left_shoulder) / body_scale
        right_arm_extension = self._distance(right_wrist, right_shoulder) / body_scale
        arms_high = left_wrist[1] < left_shoulder[1] and right_wrist[1] < right_shoulder[1]
        wrists_close = abs(left_wrist[0] - right_wrist[0]) / body_scale < 0.5
        knees_high = left_knee[1] < shoulder_mid[1] or right_knee[1] < shoulder_mid[1]
        ankles_close = abs(left_ankle[0] - right_ankle[0]) / body_scale < 0.5
        forward_drive = abs(nose[0] - hip_mid[0]) / body_scale > 0.6
        level_change = shoulder_mid[1] > hip_mid[1]

        current_position = (position or "").lower()
        if any(token in current_position for token in ("mount", "guard", "back")):
            if max(left_arm_extension, right_arm_extension) > 1.4:
                techniques.append(TechniqueCandidate("submission", "Armbar", 0.8, "Extended arm leverage detected"))

        if any(token in current_position for token in ("side_control", "mount")):
            wrist_behind_shoulder = (
                (left_wrist[1] > left_shoulder[1] and abs(left_wrist[0] - left_shoulder[0]) / body_scale > 0.3)
                or (right_wrist[1] > right_shoulder[1] and abs(right_wrist[0] - right_shoulder[0]) / body_scale > 0.3)
            )
            if wrist_behind_shoulder:
                techniques.append(TechniqueCandidate("submission", "Kimura", 0.85, "Kimura grip pattern detected"))

        if any(token in current_position for token in ("closed_guard", "open_guard")) and knees_high and ankles_close:
            techniques.append(TechniqueCandidate("submission", "Triangle Choke", 0.75, "High guard with locked legs"))

        if any(token in current_position for token in ("back", "mount")) and arms_high and wrists_close:
            techniques.append(TechniqueCandidate("submission", "Rear Naked Choke", 0.8, "Hands high and close near neck"))

        if current_position == "standing" and level_change and forward_drive:
            techniques.append(TechniqueCandidate("takedown", "Takedown", 0.7, "Level change and forward drive detected"))

        if "guard" in current_position and knees_high and forward_drive:
            techniques.append(TechniqueCandidate("sweep", "Sweep / Reversal", 0.68, "Guard elevation with forward drive"))

        return techniques

    @staticmethod
    def _midpoint(a: list[float], b: list[float]) -> list[float]:
        return [
            (a[0] + b[0]) / 2.0,
            (a[1] + b[1]) / 2.0,
            min(a[2], b[2]),
        ]

    @staticmethod
    def _distance(a: list[float], b: list[float]) -> float:
        return float(sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2))
