from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RFPositionService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = None
        self.idx_to_label: dict[int, str] = {}
        self.is_available = False
        self._load()

    def _load(self) -> None:
        model_path = Path(self.settings.rf_model_path)
        mapping_path = Path(self.settings.rf_label_mapping_path)
        if not model_path.exists() or not mapping_path.exists():
            logger.warning("RF classifier unavailable model=%s mapping=%s", model_path, mapping_path)
            return

        loaded = joblib.load(model_path)
        self.model = loaded["model"] if isinstance(loaded, dict) and "model" in loaded else loaded
        if isinstance(loaded, dict) and "label_mapping" in loaded:
            label_mapping = loaded["label_mapping"]
        else:
            with mapping_path.open("r", encoding="utf-8") as handle:
                label_mapping = json.load(handle)
        self.idx_to_label = {int(value): key for key, value in label_mapping.items()}
        self.is_available = True

    def predict(self, keypoints: list[list[float]]) -> dict[str, float | str] | None:
        if not self.is_available or len(keypoints) < 17:
            return None

        features = self._extract_features(keypoints)
        if features is None:
            return None

        prediction_idx = int(self.model.predict([features])[0])
        probabilities = self.model.predict_proba([features])[0]
        confidence = float(probabilities[prediction_idx])
        return {
            "position_base": self.idx_to_label.get(prediction_idx, "scramble"),
            "confidence": confidence,
        }

    @staticmethod
    def _extract_features(keypoints: list[list[float]]) -> list[float] | None:
        if len(keypoints) < 17:
            return None

        try:
            kp_array = np.array(keypoints, dtype=float)

            left_shoulder = kp_array[5]
            right_shoulder = kp_array[6]
            left_hip = kp_array[11]
            right_hip = kp_array[12]

            hip_cx = (left_hip[0] + right_hip[0]) / 2.0
            hip_cy = (left_hip[1] + right_hip[1]) / 2.0

            shoulder_cx = (left_shoulder[0] + right_shoulder[0]) / 2.0
            shoulder_cy = (left_shoulder[1] + right_shoulder[1]) / 2.0

            body_scale = np.sqrt((shoulder_cx - hip_cx) ** 2 + (shoulder_cy - hip_cy) ** 2)
            if body_scale < 1.0:
                body_scale = 1.0

            features: list[float] = []
            for i in range(17):
                features.append((kp_array[i, 0] - hip_cx) / body_scale)
                features.append((kp_array[i, 1] - hip_cy) / body_scale)

            avg_conf = float(np.mean(kp_array[:, 2]))
            features.append(avg_conf)
            return np.array(features, dtype=np.float32).tolist()
        except Exception:
            return None
