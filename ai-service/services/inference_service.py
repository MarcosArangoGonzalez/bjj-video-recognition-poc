import os
import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO
import logging
from typing import Dict, Any, Optional

try:
    from services.hybrid_bjj_detector import HybridBJJDetector
except ImportError as e:
    HybridBJJDetector = None
    import logging
    logging.getLogger(__name__).warning(f"HybridBJJDetector could not be imported: {e}")

logger = logging.getLogger(__name__)

KEYPOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle"
]

# COCO keypoint indices
_KP = {name: i for i, name in enumerate(KEYPOINT_NAMES)}

# Person-selection thresholds — mirrors yolov8_service.py constants
_MIN_ATHLETE_CONFIDENCE = 0.50      # standing / unclear
_GROUNDWORK_CONFIDENCE_FLOOR = 0.35 # lowered when body is horizontal (BJJ ground)
_MIN_KEYPOINTS_PER_ATHLETE = 8


def _looks_like_groundwork(kp_xy: np.ndarray, kp_conf: np.ndarray, frame_height: float) -> bool:
    """Returns True when body appears horizontal — mirrors yolov8_service.py."""
    try:
        if len(kp_xy) < 17 or len(kp_conf) < 17:
            return False
        sh_cx = (kp_xy[5][0] + kp_xy[6][0]) / 2.0
        sh_cy = (kp_xy[5][1] + kp_xy[6][1]) / 2.0
        hip_cx = (kp_xy[11][0] + kp_xy[12][0]) / 2.0
        hip_cy = (kp_xy[11][1] + kp_xy[12][1]) / 2.0
        nose_y = float(kp_xy[0][1])
        torso_height = max(np.sqrt((sh_cx - hip_cx) ** 2 + (sh_cy - hip_cy) ** 2), 1.0)
        horizontal_body = abs(nose_y - hip_cy) / torso_height < 1.55
        low_in_frame = frame_height > 0 and hip_cy / frame_height > 0.42
        torso_conf = min(float(kp_conf[5]), float(kp_conf[6]),
                         float(kp_conf[11]), float(kp_conf[12]))
        return torso_conf >= 0.2 and (horizontal_body or low_in_frame)
    except Exception:
        return False


def _select_best_athlete(result) -> Optional[int]:
    """
    Mirrors yolov8_service.py _select_supported_athletes().
    Picks the person with highest mean keypoint confidence that meets
    the confidence floor (lowered for groundwork). Returns None if no
    candidate qualifies — caller should skip the frame entirely.
    """
    kp_xy_all = result.keypoints.xy.cpu().numpy()
    kp_conf_all = result.keypoints.conf.cpu().numpy()
    frame_height = float(getattr(result, "orig_shape", [0, 0])[0] or 0.0)

    candidates = []
    for idx, (kp_xy, kp_conf) in enumerate(zip(kp_xy_all, kp_conf_all)):
        floor = (_GROUNDWORK_CONFIDENCE_FLOOR
                 if _looks_like_groundwork(kp_xy, kp_conf, frame_height)
                 else _MIN_ATHLETE_CONFIDENCE)
        support_count = int(np.sum(kp_conf >= floor))
        mean_conf = float(np.mean(kp_conf))
        if support_count >= _MIN_KEYPOINTS_PER_ATHLETE and mean_conf >= floor:
            candidates.append((idx, mean_conf))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]


def _angle(a, b, c) -> Optional[float]:
    """
    Angle at joint B between segments BA and BC, in degrees.
    Each point is [x, y, conf]. Returns None if any point has conf == 0.
    """
    try:
        if a[2] < 0.1 or b[2] < 0.1 or c[2] < 0.1:
            return None
        ba = np.array([a[0] - b[0], a[1] - b[1]], dtype=float)
        bc = np.array([c[0] - b[0], c[1] - b[1]], dtype=float)
        na, nb_ = np.linalg.norm(ba), np.linalg.norm(bc)
        if na < 1e-6 or nb_ < 1e-6:
            return None
        cos_val = np.dot(ba, bc) / (na * nb_)
        return float(round(np.degrees(np.arccos(np.clip(cos_val, -1.0, 1.0))), 1))
    except Exception:
        return None


def compute_joint_angles(keypoints_array) -> Dict[str, Optional[float]]:
    """
    Compute 6 joint angles from 17 COCO keypoints [[x, y, conf], ...].
    Returns dict matching JointAngles schema.
    """
    if not keypoints_array or len(keypoints_array) < 17:
        return {}

    kp = keypoints_array  # shorthand

    l_sh  = kp[_KP["left_shoulder"]]
    r_sh  = kp[_KP["right_shoulder"]]
    l_elb = kp[_KP["left_elbow"]]
    r_elb = kp[_KP["right_elbow"]]
    l_wr  = kp[_KP["left_wrist"]]
    r_wr  = kp[_KP["right_wrist"]]
    l_hip = kp[_KP["left_hip"]]
    r_hip = kp[_KP["right_hip"]]
    l_kn  = kp[_KP["left_knee"]]
    r_kn  = kp[_KP["right_knee"]]
    l_ank = kp[_KP["left_ankle"]]
    r_ank = kp[_KP["right_ankle"]]

    # Hip and shoulder midpoints
    hip_mid = [(l_hip[0]+r_hip[0])/2, (l_hip[1]+r_hip[1])/2, min(l_hip[2], r_hip[2])]
    sh_mid  = [(l_sh[0]+r_sh[0])/2,  (l_sh[1]+r_sh[1])/2,  min(l_sh[2], r_sh[2])]
    knee_mid= [(l_kn[0]+r_kn[0])/2,  (l_kn[1]+r_kn[1])/2,  min(l_kn[2], r_kn[2])]

    # Spine tilt: angle of spine (hip→shoulder) relative to vertical [0, -1]
    # hip_spine_angle: angle at hip between shoulder and knee midpoints
    # spine_tilt_angle: absolute tilt of spine from vertical in degrees
    spine_tilt = None
    try:
        dx = sh_mid[0] - hip_mid[0]
        dy = sh_mid[1] - hip_mid[1]
        length = np.sqrt(dx**2 + dy**2)
        if length > 1.0 and sh_mid[2] > 0.1 and hip_mid[2] > 0.1:
            # Angle from vertical (pointing up = -y in image coords)
            spine_tilt = float(round(np.degrees(np.arctan2(abs(dx), abs(dy))), 1))
    except Exception:
        pass

    return {
        "left_elbow_angle":  _angle(l_sh,  l_elb, l_wr),
        "right_elbow_angle": _angle(r_sh,  r_elb, r_wr),
        "left_knee_angle":   _angle(l_hip, l_kn,  l_ank),
        "right_knee_angle":  _angle(r_hip, r_kn,  r_ank),
        "hip_spine_angle":   _angle(sh_mid, hip_mid, knee_mid),
        "spine_tilt_angle":  spine_tilt,
    }


class InferenceService:
    def __init__(self):
        self.model = None
        self.hybrid_detector = None

        self.use_gpu = os.getenv('USE_GPU', 'true').lower() == 'true'
        self.model_path = self._resolve_artifact_path(
            "MODEL_PATH",
            ["/app/artifacts/bjj_custom.pt", "/app/artifacts/yolov8n-pose.pt", "../python/models/bjj_custom.pt", "../yolov8n-pose.pt", "yolov8n-pose.pt"],
        )
        self.local_model_path = self._resolve_artifact_path(
            "LOCAL_MODEL_PATH",
            ["/app/artifacts/bjj_pose_classifier.pkl", "../python/models/bjj_pose_classifier.pkl"],
        )
        self.label_mapping_path = self._resolve_artifact_path(
            "LABEL_MAPPING_PATH",
            ["/app/artifacts/label_mapping.json", "../python/models/label_mapping.json"],
        )

    def is_loaded(self):
        return self.model is not None

    @staticmethod
    def _resolve_artifact_path(env_var: str, candidates: list[str]) -> str:
        explicit = os.getenv(env_var)
        if explicit:
            return explicit
        for candidate in candidates:
            if Path(candidate).exists():
                return candidate
        return candidates[0]

    def load_model(self):
        if self.model is not None:
            return self.model

        try:
            if Path(self.model_path).exists():
                logger.info(f"Loading custom BJJ model from {self.model_path}")
                self.model = YOLO(self.model_path)
            else:
                logger.info("Loading base YOLOv8-pose model (Fallback)")
                yolo_fallback = '../yolov8n-pose.pt' if Path('../yolov8n-pose.pt').exists() else 'yolov8n-pose.pt'
                self.model = YOLO(yolo_fallback)

            device = 'cuda:0' if self.use_gpu and cv2.cuda.getCudaEnabledDeviceCount() > 0 else 'cpu'
            logger.info(f"Using device: {device}")

            if HybridBJJDetector:
                try:
                    logger.info("Initializing Hybrid BJJ Detector...")
                    self.hybrid_detector = HybridBJJDetector(
                        local_model_path=self.local_model_path,
                        label_mapping_path=self.label_mapping_path
                    )
                    self.hybrid_detector.reset_sequence_state()
                    logger.info("✓ Hybrid detector initialized")
                except Exception as e:
                    logger.warning(f"Hybrid detector initialization failed: {e}")
                    self.hybrid_detector = None

            return self.model
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            raise

    def analyze_frame(self, frame: np.ndarray, frame_number: int = 1, timestamp_seconds: float = 0.0, frame_image_path: str = None) -> Dict[str, Any]:
        results = self.model(frame, verbose=False)
        if len(results) > 0:
            return self.extract_keypoints_from_result(results[0], frame_number, timestamp_seconds, frame_image_path)
        return self._empty_frame_data(frame_number, timestamp_seconds)

    def extract_keypoints_from_result(self, result, frame_number, timestamp_seconds, frame_image_path=None):
        frame_data = self._empty_frame_data(frame_number, timestamp_seconds)

        if result.keypoints is None or len(result.keypoints) == 0:
            return frame_data

        # Mirrors yolov8_service.py _select_supported_athletes():
        # pick best-confidence athlete that meets the floor (lower for groundwork).
        # If no candidate qualifies, skip this frame entirely.
        best_idx = _select_best_athlete(result)
        if best_idx is None:
            logger.debug(f"[person_select] Frame {frame_number}: no qualifying athlete — skipped")
            return frame_data

        keypoints_xy = result.keypoints.xy[best_idx].cpu().numpy()
        keypoints_conf = result.keypoints.conf[best_idx].cpu().numpy()

        kp_dicts = []
        kp_array = []
        for i, (xy, conf) in enumerate(zip(keypoints_xy, keypoints_conf)):
            if i < len(KEYPOINT_NAMES):
                kp_dicts.append({
                    "name": KEYPOINT_NAMES[i],
                    "x": float(xy[0]),
                    "y": float(xy[1]),
                    "confidence": float(conf)
                })
                kp_array.append([float(xy[0]), float(xy[1]), float(conf)])

        frame_data["keypoints"] = kp_dicts
        frame_data["confidence"] = float(np.mean(keypoints_conf))

        if result.boxes is not None and len(result.boxes) > 0:
            box = result.boxes[best_idx]
            bbox = box.xyxy[0].cpu().numpy()
            frame_data["boundingBoxes"].append({
                "x1": float(bbox[0]),
                "y1": float(bbox[1]),
                "x2": float(bbox[2]),
                "y2": float(bbox[3]),
                "confidence": float(box.conf[0])
            })

        hybrid_results = self.predict_bjj_position(kp_dicts, frame_image_path)

        if isinstance(hybrid_results, dict):
            frame_data["predictedPosition"] = hybrid_results.get("position")
            frame_data["positionConfidence"] = hybrid_results.get("positionConfidence", 0.0)
            frame_data["detectedSubmissions"] = hybrid_results.get("submissions", [])
            frame_data["detectedSweeps"] = hybrid_results.get("sweeps", [])
            frame_data["detectedTransitions"] = hybrid_results.get("transitions", [])
            frame_data["detectedTakedowns"] = hybrid_results.get("takedowns", [])
            frame_data["allTechniques"] = hybrid_results.get("all_techniques", [])

            # Joint angles: prefer detector's _calculate_joint_angles() output,
            # supplement with hip_spine_angle from our computation (detector doesn't compute it)
            detector_angles = hybrid_results.get("joint_angles") or {}
            if not detector_angles:
                detector_angles = compute_joint_angles(kp_array)
            elif "hip_spine_angle" not in detector_angles:
                supplemental = compute_joint_angles(kp_array)
                detector_angles["hip_spine_angle"] = supplemental.get("hip_spine_angle")
            frame_data["joint_angles"] = detector_angles
        else:
            frame_data["predictedPosition"] = hybrid_results
            frame_data["positionConfidence"] = 0.5
            frame_data["joint_angles"] = compute_joint_angles(kp_array)

        return frame_data

    def predict_bjj_position(self, keypoints, frame_image_path=None):
        if not self.hybrid_detector:
            return {
                "position": "unknown",
                "positionConfidence": 0.0,
                "submissions": [],
                "sweeps": [],
                "transitions": [],
                "takedowns": [],
                "all_techniques": [],
            }

        try:
            keypoints_array = [
                [kp.get("x", 0), kp.get("y", 0), kp.get("confidence", 0)]
                for kp in keypoints
            ]

            results = self.hybrid_detector.hybrid_predict(
                keypoints=keypoints_array,
                image_path=frame_image_path
            )

            return {
                "position": results.get("position"),
                "positionConfidence": results.get("position_confidence", 0.0),
                "submissions": results.get("submissions", []),
                "sweeps": results.get("sweeps", []),
                "transitions": results.get("transitions", []),
                "takedowns": results.get("takedowns", []),
                "all_techniques": results.get("all_techniques", [])
            }

        except Exception as e:
            logger.error(f"Hybrid detection error: {e}")
            return {
                "position": "unknown",
                "positionConfidence": 0.0,
                "submissions": [],
                "sweeps": [],
                "transitions": [],
                "takedowns": [],
                "all_techniques": [],
            }

    def _empty_frame_data(self, frame_number, timestamp):
        return {
            "frameNumber": frame_number,
            "timestampSeconds": timestamp,
            "keypoints": [],
            "predictedPosition": "NO_DATA",
            "confidence": 0.0,
            "positionConfidence": 0.0,
            "boundingBoxes": [],
            "allTechniques": [],
            "detectedSubmissions": [],
            "detectedSweeps": [],
            "detectedTransitions": [],
            "joint_angles": {},
        }


inference_service = InferenceService()
