from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8081
    log_level: str = "INFO"

    ai_webhook_secret: str = "dev-secret-change-in-prod"
    local_storage_dir: str = "/app/videos"
    analysis_fps: float = 2.0
    webhook_timeout_seconds: float = 15.0
    webhook_max_retries: int = 2
    webhook_retry_backoff_seconds: float = 1.5

    yolo_model_path: str = "/app/artifacts/yolov8n-pose.pt"
    yolo_confidence_threshold: float = 0.35
    rf_model_path: str = "/app/artifacts/bjj_pose_classifier.pkl"
    rf_label_mapping_path: str = "/app/artifacts/label_mapping.json"
    max_frames_per_video: int = Field(default=0, description="0 disables the cap")
    python_parity_mode: bool = True
    spring_poc_enabled: bool = False
    spring_poc_base_url: str = "http://localhost:8090"
    spring_poc_timeout_seconds: float = 300.0
    spring_poc_poll_interval_seconds: float = 2.0
    spring_poc_max_wait_seconds: float = 240.0
    gemini_enabled: bool = False
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    gemini_timeout_seconds: float = 45.0
    gemini_max_frames: int = 8
    gemini_sample_interval_seconds: float = 2.0
    debug_frame_decisions: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
