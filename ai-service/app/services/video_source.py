from pathlib import Path
import logging

from app.config import Settings

logger = logging.getLogger(__name__)

class VideoSourceResolver:
    def __init__(self, settings: Settings):
        self._local_storage_dir = Path(settings.local_storage_dir)

    def resolve(self, video_url: str) -> str:
        if video_url.startswith("local:"):
            filename = video_url[len("local:") :].strip()
            if not filename:
                raise ValueError("Empty local video filename")
            local_path = (self._local_storage_dir / filename).resolve()
            if not local_path.exists():
                raise FileNotFoundError(f"Local video file not found: {local_path}")
            if not local_path.is_file():
                raise FileNotFoundError(f"Local video path is not a file: {local_path}")
            logger.info("Resolved local video source video_url=%s path=%s", video_url, local_path)
            return str(local_path)

        if video_url.startswith("http://") or video_url.startswith("https://"):
            return video_url

        raise ValueError(f"Unsupported video_url scheme: {video_url}")
