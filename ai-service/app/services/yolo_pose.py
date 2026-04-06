from __future__ import annotations

from pathlib import Path

import numpy as np

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class YoloPoseService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = None
        self.is_available = Path(self.settings.yolo_model_path).exists()

    def _load(self) -> None:
        if self.model is not None:
            return
        try:
            from ultralytics import YOLO
        except Exception as exc:  # pragma: no cover
            logger.warning("Ultralytics import failed: %s", exc)
            self.is_available = False
            return
        model_path = Path(self.settings.yolo_model_path)
        if not model_path.exists():
            logger.warning("YOLO model not found at %s", model_path)
            self.is_available = False
            return
        self.model = YOLO(str(model_path))
        self.is_available = True

    def infer_keypoints(self, frame: np.ndarray) -> list[list[float]]:
        if self.model is None:
            self._load()
        if not self.is_available or self.model is None:
            return []
        results = self.model(frame, verbose=False, conf=self.settings.yolo_confidence_threshold)
        if not results:
            return []
        result = results[0]
        if result.keypoints is None or len(result.keypoints) == 0:
            return []
        keypoints_xy = result.keypoints.xy[0].cpu().numpy()
        keypoints_conf = result.keypoints.conf[0].cpu().numpy()
        return [
            [float(xy[0]), float(xy[1]), float(conf)]
            for xy, conf in zip(keypoints_xy, keypoints_conf)
        ]
