from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SpringPocClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _is_youtube_url(self, video_path: str) -> bool:
        parsed = urlparse(video_path)
        host = (parsed.netloc or "").lower()
        return "youtube.com" in host or "youtu.be" in host

    def _download_with_ytdlp(self, video_path: str) -> tuple[Path, TemporaryDirectory[str]]:
        ytdlp = shutil.which("yt-dlp")
        if ytdlp is None:
            raise RuntimeError("yt-dlp is required to analyze YouTube URLs")

        temp_dir = TemporaryDirectory(prefix="bjj-ytdlp-")
        output_template = str(Path(temp_dir.name) / "video.%(ext)s")
        command = [
            ytdlp,
            "--no-playlist",
            "--format",
            "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
            "--output",
            output_template,
            video_path,
        ]
        logger.info("Downloading YouTube source via yt-dlp url=%s", video_path)
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            temp_dir.cleanup()
            stderr = (exc.stderr or exc.stdout or "").strip()
            raise RuntimeError(f"yt-dlp failed to download YouTube video: {stderr}") from exc

        files = sorted(Path(temp_dir.name).glob("video.*"))
        if not files:
            temp_dir.cleanup()
            raise FileNotFoundError("yt-dlp did not produce a downloadable video file")

        logger.info("Downloaded YouTube video url=%s path=%s", video_path, files[0])
        return files[0], temp_dir

    def _download_remote_file(self, video_path: str) -> tuple[Path, Path]:
        suffix = Path(urlparse(video_path).path).suffix or ".mp4"
        with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            temp_path = Path(tmp.name)
            with httpx.Client(
                timeout=self.settings.spring_poc_timeout_seconds,
                follow_redirects=True,
            ) as client:
                with client.stream("GET", video_path) as response:
                    response.raise_for_status()
                    for chunk in response.iter_bytes():
                        if chunk:
                            tmp.write(chunk)
        logger.info("Downloaded remote video source url=%s path=%s", video_path, temp_path)
        return temp_path, temp_path

    def _materialize_video_source(self, video_path: str) -> tuple[Path, object | None]:
        parsed = urlparse(video_path)
        if parsed.scheme in {"http", "https"}:
            if self._is_youtube_url(video_path):
                return self._download_with_ytdlp(video_path)
            return self._download_remote_file(video_path)

        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {path}")
        return path, None

    def _cleanup_source(self, cleanup_target: object | None) -> None:
        if cleanup_target is None:
            return
        try:
            if isinstance(cleanup_target, TemporaryDirectory):
                cleanup_target.cleanup()
            elif isinstance(cleanup_target, Path):
                cleanup_target.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove temporary downloaded video artifact=%s", cleanup_target)

    def analyze_video(self, video_path: str) -> dict[str, Any]:
        path, cleanup_target = self._materialize_video_source(video_path)

        try:
            with httpx.Client(
                base_url=self.settings.spring_poc_base_url,
                timeout=self.settings.spring_poc_timeout_seconds,
            ) as client:
                with path.open("rb") as handle:
                    files = {"file": (path.name, handle, "video/mp4")}
                    logger.info("Uploading video to Spring PoC filename=%s", path.name)
                    response = client.post("/api/videos/upload", files=files)
                    response.raise_for_status()
                upload_dto = response.json()
                video_id = int(upload_dto["id"])
                status = str(upload_dto.get("analysisStatus", "")).upper()
                logger.info(
                    "Spring PoC upload finished video_id=%s filename=%s status=%s",
                    video_id,
                    upload_dto.get("filename"),
                    status,
                )

                if status == "FAILED":
                    error_message = upload_dto.get("analysisError") or "Spring PoC analysis failed"
                    raise RuntimeError(error_message)

                deadline = time.monotonic() + self.settings.spring_poc_max_wait_seconds
                last_status = None
                while time.monotonic() < deadline:
                    status_response = client.get(f"/api/videos/{video_id}")
                    status_response.raise_for_status()
                    video_dto = status_response.json()
                    status = str(video_dto.get("analysisStatus", "")).upper()
                    tag_count = len(list(video_dto.get("tags", []) or []))
                    if status != last_status:
                        logger.info(
                            "Spring PoC analysis status video_id=%s status=%s tags=%s",
                            video_id,
                            status,
                            tag_count,
                        )
                        last_status = status
                    if status == "COMPLETED":
                        if tag_count > 0:
                            return video_dto
                        logger.info(
                            "Spring PoC video_id=%s completed but tags are still empty; retrying",
                            video_id,
                        )
                    if status == "FAILED":
                        error_message = video_dto.get("analysisError") or "Spring PoC analysis failed"
                        raise RuntimeError(error_message)
                    time.sleep(self.settings.spring_poc_poll_interval_seconds)

            raise TimeoutError(
                f"Spring PoC analysis timed out after {self.settings.spring_poc_max_wait_seconds}s for video {path.name}"
            )
        finally:
            self._cleanup_source(cleanup_target)
