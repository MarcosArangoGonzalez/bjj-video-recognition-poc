from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SpringPocClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def analyze_video(self, video_path: str) -> dict[str, Any]:
        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {path}")

        with httpx.Client(base_url=self.settings.spring_poc_base_url, timeout=self.settings.spring_poc_timeout_seconds) as client:
            with path.open("rb") as handle:
                files = {"file": (path.name, handle, "video/mp4")}
                logger.info("Uploading video to Spring PoC filename=%s", path.name)
                response = client.post("/api/videos/upload", files=files)
                response.raise_for_status()
            upload_dto = response.json()
            video_id = int(upload_dto["id"])
            status = str(upload_dto.get("analysisStatus", "")).upper()
            logger.info("Spring PoC upload finished video_id=%s filename=%s status=%s", video_id, upload_dto.get("filename"), status)

            if status == "FAILED":
                error_message = upload_dto.get("analysisError") or "Spring PoC analysis failed"
                raise RuntimeError(error_message)

            # The upload endpoint can return COMPLETED before the serialized tag list is fully visible.
            # Always re-fetch by id so the wrapper consumes the same representation that the PoC UI loads.
            deadline = time.monotonic() + self.settings.spring_poc_max_wait_seconds
            last_status = None
            while time.monotonic() < deadline:
                status_response = client.get(f"/api/videos/{video_id}")
                status_response.raise_for_status()
                video_dto = status_response.json()
                status = str(video_dto.get("analysisStatus", "")).upper()
                tag_count = len(list(video_dto.get("tags", []) or []))
                if status != last_status:
                    logger.info("Spring PoC analysis status video_id=%s status=%s tags=%s", video_id, status, tag_count)
                    last_status = status
                if status == "COMPLETED":
                    if tag_count > 0:
                        return video_dto
                    logger.info("Spring PoC video_id=%s completed but tags are still empty; retrying", video_id)
                if status == "FAILED":
                    error_message = video_dto.get("analysisError") or "Spring PoC analysis failed"
                    raise RuntimeError(error_message)
                time.sleep(self.settings.spring_poc_poll_interval_seconds)

        raise TimeoutError(
            f"Spring PoC analysis timed out after {self.settings.spring_poc_max_wait_seconds}s for video {path.name}"
        )
