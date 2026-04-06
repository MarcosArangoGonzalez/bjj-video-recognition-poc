from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class AnalysisRequest(BaseModel):
    publication_id: str = Field(..., min_length=1)
    video_url: str = Field(..., min_length=1)
    callback_url: str = Field(..., min_length=1)
    user_belt: str = "white"
    auto_tag: bool = True
    biometric_tracking: bool = False

    @field_validator("publication_id")
    @classmethod
    def validate_publication_id(cls, value: str) -> str:
        value = value.strip()
        int(value)
        return value

    @field_validator("video_url", "callback_url", "user_belt")
    @classmethod
    def strip_strings(cls, value: str) -> str:
        return value.strip()


class AnalysisAcceptedResponse(BaseModel):
    status: str = "accepted"
    publication_id: int


class JointAngles(BaseModel):
    left_elbow_angle: Optional[float] = None
    right_elbow_angle: Optional[float] = None
    left_knee_angle: Optional[float] = None
    right_knee_angle: Optional[float] = None
    hip_spine_angle: Optional[float] = None
    spine_tilt_angle: Optional[float] = None


class DetectedFrameDto(BaseModel):
    frame_index: int
    timestamp_seconds: float
    detected_class: str
    confidence: float
    joint_angles: Optional[JointAngles] = None
    feedback: Optional[str] = None
    suggested_tags: Optional[list[dict[str, Any]]] = None
    player_role: Optional[str] = None


class WebhookPayload(BaseModel):
    publication_id: int
    status: str
    frames: Optional[list[DetectedFrameDto]] = None
    combat_story: Optional[list[dict[str, Any]]] = None
    error_message: Optional[str] = None
    primary_detected_class: Optional[str] = None


@dataclass(slots=True)
class AnalysisResult:
    publication_id: int
    status: str
    frames: list[Any] | None = None
    combat_story: list[dict[str, Any]] | None = None
    error_message: str | None = None
    primary_detected_class: str | None = None

    def to_webhook_payload(self) -> WebhookPayload:
        return WebhookPayload(
            publication_id=self.publication_id,
            status=self.status,
            frames=self.frames,
            combat_story=self.combat_story,
            error_message=self.error_message,
            primary_detected_class=self.primary_detected_class,
        )
