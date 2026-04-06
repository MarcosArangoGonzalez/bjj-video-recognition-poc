"""
YOLOv8 BJJ Pose Detection Microservice
Provides REST API for video analysis using hybrid Roboflow + annotations.json models
"""

import os
import traceback
from pathlib import Path
try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
except Exception:
    Flask = None
    request = None
    jsonify = None
    CORS = None
try:
    from werkzeug.utils import secure_filename
except Exception:
    def secure_filename(value):
        return Path(str(value or "")).name
import cv2
import numpy as np
from ultralytics import YOLO
from dotenv import load_dotenv
from hybrid_bjj_detector import HybridBJJDetector

# Load environment variables
load_dotenv()

if Flask is not None:
    app = Flask(__name__)
    if CORS is not None:
        CORS(app)
else:
    class _AppStub:
        def __init__(self):
            import logging

            self.logger = logging.getLogger(__name__)
            self.config = {}

        def route(self, *_args, **_kwargs):
            def decorator(func):
                return func
            return decorator

    app = _AppStub()

# Configuration
UPLOAD_FOLDER = Path('temp_frames')
UPLOAD_FOLDER.mkdir(exist_ok=True)
MODEL_PATH = os.getenv('MODEL_PATH', 'models/bjj_custom.pt')
LOCAL_MODEL_PATH = os.getenv('LOCAL_MODEL_PATH', 'models/bjj_pose_classifier.pkl')
LABEL_MAPPING_PATH = os.getenv('LABEL_MAPPING_PATH', 'models/label_mapping.json')
USE_GPU = os.getenv('USE_GPU', 'true').lower() == 'true'
DEFAULT_FPS = int(os.getenv('DEFAULT_FPS', '1'))
MAX_VIDEO_SIZE_MB = int(os.getenv('MAX_VIDEO_SIZE_MB', '500'))

app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = MAX_VIDEO_SIZE_MB * 1024 * 1024

# Global model instances
model = None
hybrid_detector = None

# COCO keypoint names for YOLOv8-pose
KEYPOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle"
]


def load_model():
    """Load YOLOv8 pose model and hybrid detector"""
    global model, hybrid_detector
    
    if model is not None:
        return model
    
    try:
        # Try to load custom fine-tuned model first
        if Path(MODEL_PATH).exists():
            app.logger.info(f"Loading custom BJJ model from {MODEL_PATH}")
            model = YOLO(MODEL_PATH)
        else:
            # Fallback to base YOLOv8-pose model
            app.logger.info("Loading base YOLOv8-pose model")
            model = YOLO('yolov8n-pose.pt')
        
        # Set device (GPU if available)
        device = 'cuda:0' if USE_GPU and cv2.cuda.getCudaEnabledDeviceCount() > 0 else 'cpu'
        app.logger.info(f"Using device: {device}")
        
        # Initialize hybrid detector
        try:
            app.logger.info("Initializing Hybrid BJJ Detector...")
            hybrid_detector = HybridBJJDetector(
                local_model_path=LOCAL_MODEL_PATH,
                label_mapping_path=LABEL_MAPPING_PATH
            )
            app.logger.info("✓ Hybrid detector initialized (Local + Roboflow)")
        except Exception as e:
            app.logger.warning(f"Hybrid detector initialization failed: {e}")
            app.logger.warning("Falling back to basic detection")
            hybrid_detector = None
        
        return model
    except Exception as e:
        app.logger.error(f"Error loading model: {str(e)}")
        raise

#Takes a YOLOv8 result and returns a dictionary with the keypoints, position prediction, confidence
def extract_keypoints_from_result(result, frame_number, timestamp_seconds, frame_image_path=None):
    """
    Extract structured keypoint data from YOLOv8 result
    
    Args:
        result: YOLOv8 inference result
        frame_number: Frame index
        timestamp_seconds: Timestamp in video
        frame_image_path: Path to saved frame image for Roboflow analysis
    
    Returns:
        dict: Frame data with keypoints, position prediction, confidence
    """
    frame_data = {
        "frameNumber": frame_number,
        "timestampSeconds": timestamp_seconds,
        "keypoints": [],
        "predictedPosition": None,
        "confidence": 0.0,
        "boundingBoxes": []
    }
    
    if result.keypoints is None or len(result.keypoints) == 0:
        return frame_data
    
    # Get first person detected (primary athlete)
    keypoints_xy = result.keypoints.xy[0].cpu().numpy() 
    keypoints_conf = result.keypoints.conf[0].cpu().numpy() 
    
    # Convert to structured format
    for i, (xy, conf) in enumerate(zip(keypoints_xy, keypoints_conf)):
        if i < len(KEYPOINT_NAMES):
            frame_data["keypoints"].append({
                "name": KEYPOINT_NAMES[i],
                "x": float(xy[0]),
                "y": float(xy[1]),
                "confidence": float(conf)
            })
    
    # Calculate average confidence
    frame_data["confidence"] = float(np.mean(keypoints_conf))
    
    # Extract bounding boxes if available
    if result.boxes is not None and len(result.boxes) > 0:
        for box in result.boxes:
            bbox = box.xyxy[0].cpu().numpy()
            frame_data["boundingBoxes"].append({
                "x1": float(bbox[0]),
                "y1": float(bbox[1]),
                "x2": float(bbox[2]),
                "y2": float(bbox[3]),
                "confidence": float(box.conf[0])
            })
    
    # Hybrid BJJ technique detection (positions + submissions + sweeps + transitions)
    hybrid_results = predict_bjj_position(frame_data["keypoints"], frame_image_path=frame_image_path)
    
    # Integrate hybrid results
    if isinstance(hybrid_results, dict):
        frame_data["predictedPosition"] = hybrid_results.get("position")
        frame_data["positionConfidence"] = hybrid_results.get("positionConfidence", 0.0)
        frame_data["detectedSubmissions"] = hybrid_results.get("submissions", [])
        frame_data["detectedSweeps"] = hybrid_results.get("sweeps", [])
        frame_data["detectedTransitions"] = hybrid_results.get("transitions", [])
        frame_data["allTechniques"] = hybrid_results.get("all_techniques", [])
    else:
        # Fallback for legacy string return
        frame_data["predictedPosition"] = hybrid_results
        frame_data["positionConfidence"] = 0.5
    
    return frame_data


def predict_bjj_position(keypoints, frame_image_path=None):
    """
    Predict BJJ techniques using hybrid detector
    
    Strategy:
    - Local classifier for positions (95.6% accuracy)
    - Roboflow for submissions, sweeps, transitions
    
    Args:
        keypoints: List of keypoint dicts from YOLOv8
        frame_image_path: Optional path to frame image for Roboflow detection
    
    Returns:
        dict: Complete technique analysis
    """
    global hybrid_detector
    
    if not hybrid_detector:
        # Fallback to simple heuristic if hybrid detector unavailable
        return _fallback_position_prediction(keypoints)
    
    try:
        # Convert keypoints to format expected by hybrid detector
        # Format: [[x, y, conf], [x, y, conf], ...] for 17 keypoints
        keypoints_array = []
        for kp_dict in keypoints:
            keypoints_array.append([
                kp_dict.get("x", 0),
                kp_dict.get("y", 0),
                kp_dict.get("confidence", 0)
            ])
        
        # Run hybrid prediction
        results = hybrid_detector.hybrid_predict(
            keypoints=keypoints_array,
            image_path=frame_image_path
        )
        
        # Return comprehensive results
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
        app.logger.error(f"Hybrid detection error: {e}")
        return _fallback_position_prediction(keypoints)


def _fallback_position_prediction(keypoints):
    """Simple heuristic-based fallback when hybrid detector unavailable"""
    if not keypoints or len(keypoints) < 17:
        return {"position": "unknown", "positionConfidence": 0.0}
    
    # Simple heuristic: check if person is upright (standing) or horizontal (ground)
    try:
        nose_y = next(kp["y"] for kp in keypoints if kp["name"] == "nose")
        left_ankle_y = next(kp["y"] for kp in keypoints if kp["name"] == "left_ankle")
        
        # If nose is significantly higher than ankles, likely standing
        vertical_distance = abs(nose_y - left_ankle_y)
        
        if vertical_distance > 300:  # Threshold in pixels
            return {"position": "standing", "positionConfidence": 0.5}
        else:
            return {"position": "ground_position", "positionConfidence": 0.3}
    except (StopIteration, KeyError):
        return {"position": "unknown", "positionConfidence": 0.0}


def analyze_video_file(video_path_str, fps=2.0):
    """
    Analyze an existing video file without running the Flask server.
    Mirrors the original endpoint logic as closely as possible.
    """
    video_path = Path(video_path_str)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    app.logger.info(f"Analyzing video file at {fps} FPS for maximum accuracy: {video_path.name}")

    frames_dir = Path(app.config['UPLOAD_FOLDER']) / 'frames' / video_path.stem
    frames_dir.mkdir(parents=True, exist_ok=True)

    model = load_model()
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open video file: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames_in_video = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if video_fps <= 0:
        raise RuntimeError(f"Invalid video metadata for {video_path}: fps={video_fps}")
    frame_interval = max(1, int(video_fps / fps))

    app.logger.info(f"Video FPS: {video_fps}, sampling every {frame_interval} frames")

    frames_data = []
    frame_count = 0
    processed_count = 0

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if frame is None or frame.size == 0:
                frame_count += 1
                continue

            if frame_count % frame_interval == 0:
                timestamp = frame_count / video_fps
                frame_filename = f"frame_{processed_count:04d}.jpg"
                frame_path = frames_dir / frame_filename
                cv2.imwrite(str(frame_path), frame)

                results = model(frame, verbose=False)
                if len(results) > 0:
                    frame_data = extract_keypoints_from_result(
                        results[0],
                        processed_count,
                        timestamp,
                        frame_image_path=str(frame_path)
                    )
                    frames_data.append(frame_data)

                processed_count += 1

            frame_count += 1
    finally:
        cap.release()
        for frame_file in frames_dir.glob("*.jpg"):
            try:
                frame_file.unlink()
            except OSError:
                pass
        try:
            frames_dir.rmdir()
        except OSError:
            pass

    app.logger.info(f"Processed {processed_count} frames from {total_frames_in_video} total frames")

    pos_scores = {}
    for frame in frames_data:
        p = frame.get("predictedPosition")
        c = frame.get("positionConfidence", 0.0)
        if p and p != "unknown":
            if p not in pos_scores:
                pos_scores[p] = {"count": 0, "total_conf": 0.0}
            pos_scores[p]["count"] += 1
            pos_scores[p]["total_conf"] += c

    best_pos = None
    best_score = -1.0
    for p, stats in pos_scores.items():
        score = stats["count"] * (stats["total_conf"] / stats["count"])
        if score > best_score:
            best_score = score
            best_pos = p

    if best_pos:
        app.logger.info(f"Stabilizing video position to: {best_pos} (score: {best_score:.2f})")
        for frame in frames_data:
            frame["predictedPosition"] = best_pos
            avg_winner_conf = pos_scores[best_pos]["total_conf"] / pos_scores[best_pos]["count"]
            frame["positionConfidence"] = avg_winner_conf
            if "allTechniques" in frame:
                filtered_techs = []
                for t in frame["allTechniques"]:
                    if t.get("type", "").upper() == "POSITION":
                        if t.get("name") == best_pos:
                            filtered_techs.append(t)
                    else:
                        filtered_techs.append(t)
                has_winner = any(t.get("name") == best_pos for t in filtered_techs)
                if not has_winner:
                    filtered_techs.append({
                        "type": "position",
                        "name": best_pos,
                        "confidence": avg_winner_conf,
                        "source": "majority_vote",
                        "reasoning": "Stabilized by majority vote"
                    })
                frame["allTechniques"] = filtered_techs

    return {
        "videoId": video_path.name,
        "totalFrames": processed_count,
        "samplingFps": fps,
        "frames": frames_data
    }


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Verify model is loaded
        load_model()
        return jsonify({
            "status": "healthy",
            "model_loaded": model is not None,
            "device": "cuda" if USE_GPU else "cpu"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500


@app.route('/api/analyze-video', methods=['POST'])
def analyze_video():
    """
    Analyze entire video for pose detection with FULL HYBRID DETECTION
    
    Request:
        - video: Video file (multipart/form-data)
        - fps: Frames per second to sample (optional, default: 2 for better coverage)
    
    Response:
        {
          "videoId": "...",
          "totalFrames": 60,
          "frames": [... frame data with positions + submissions + sweeps + transitions ...]
        }
    """
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided"}), 400
    
    video_file = request.files['video']
    if video_file.filename == '':
        return jsonify({"error": "Empty filename"}), 400
    
    # Get FPS parameter (default 2 for better technique coverage)
    fps = float(request.form.get('fps', '2'))
    app.logger.info(f"Analyzing video at {fps} FPS for maximum accuracy")
    
    try:
        # Save video temporarily
        filename = secure_filename(video_file.filename)
        video_path = Path(app.config['UPLOAD_FOLDER']) / filename
        video_file.save(str(video_path))
        
        # Create frames directory for Roboflow analysis
        frames_dir = Path(app.config['UPLOAD_FOLDER']) / 'frames' / filename.replace('.', '_')
        frames_dir.mkdir(parents=True, exist_ok=True)
        
        # Load model
        model = load_model()
        
        # Open video
        cap = cv2.VideoCapture(str(video_path))
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames_in_video = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_interval = max(1, int(video_fps / fps))
        
        app.logger.info(f"Video FPS: {video_fps}, sampling every {frame_interval} frames")
        
        frames_data = []
        frame_count = 0
        processed_count = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Sample frames at specified FPS
            if frame_count % frame_interval == 0:
                timestamp = frame_count / video_fps
                
                # Save frame image for Roboflow analysis
                frame_filename = f"frame_{processed_count:04d}.jpg"
                frame_path = frames_dir / frame_filename
                cv2.imwrite(str(frame_path), frame)
                
                # Run YOLOv8 pose detection
                results = model(frame, verbose=False)
                
                if len(results) > 0:
                    frame_data = extract_keypoints_from_result(
                        results[0], 
                        processed_count, 
                        timestamp,
                        frame_image_path=str(frame_path)  # Pass image path for Roboflow
                    )
                    frames_data.append(frame_data)
                
                processed_count += 1
            
            frame_count += 1
        
        cap.release()
        
        # Clean up video file
        video_path.unlink()
        
        app.logger.info(f"Processed {processed_count} frames from {total_frames_in_video} total frames")
        
        # --- MAJORITY VOTING FOR STABILITY ---
        # 1. Collect all position predictions
        pos_scores = {}
        for frame in frames_data:
            p = frame.get("predictedPosition")
            c = frame.get("positionConfidence", 0.0)
            if p and p != "unknown":
                if p not in pos_scores:
                    pos_scores[p] = {"count": 0, "total_conf": 0.0}
                pos_scores[p]["count"] += 1
                pos_scores[p]["total_conf"] += c
        
        # 2. Determine winner (score = count * avg_conf)
        best_pos = None
        best_score = -1.0
        
        for p, stats in pos_scores.items():
            # Grouping variants (optional? For now just raw labels)
            # bias towards mount/side_control/back/guard over transitionary states?
            score = stats["count"] * (stats["total_conf"] / stats["count"]) # basically sum of confidences
            if score > best_score:
                best_score = score
                best_pos = p
        
        # 3. Enforce winner on all frames (Stabilization)
        if best_pos:
            app.logger.info(f"Stabilizing video position to: {best_pos} (score: {best_score:.2f})")
            for frame in frames_data:
                # Update main position
                frame["predictedPosition"] = best_pos
                # Keep original confidence or boost it? Keep original but ensure it's high enough to be picked?
                # Actually Java uses the confidence from the frame.
                # If the frame originally had "guard" at 0.4, and we force "mount", 
                # we should probably give it a reasonable confidence or keep the original if it's high?
                # Let's just set it to the max confidence seen for that position, or a high default?
                # Simpler: just keep the frame's confidence but change the label.
                # But if the classifier thought it was 'guard' (0.8), and we say 'mount', 
                # confidence 0.8 for mount is a lie.
                # Let's use the average confidence of the winner.
                avg_winner_conf = pos_scores[best_pos]["total_conf"] / pos_scores[best_pos]["count"]
                frame["positionConfidence"] = avg_winner_conf
                
                # Also filter 'all_techniques' / 'allTechniques' to remove competing positions
                # This prevents Java from picking up "secondary" positions that we just overruled
                if "allTechniques" in frame:
                    filtered_techs = []
                    for t in frame["allTechniques"]:
                        # Keep submissions/sweeps/etc, but filter POSITIONS that aren't the winner
                        if t.get("type", "").upper() == "POSITION":
                            if t.get("name") == best_pos:
                                filtered_techs.append(t)
                        else:
                            filtered_techs.append(t)
                    
                    # Ensure the winner is in allTechniques
                    has_winner = any(t.get("name") == best_pos for t in filtered_techs)
                    if not has_winner:
                        filtered_techs.append({
                            "type": "position",
                            "name": best_pos,
                            "confidence": avg_winner_conf,
                            "source": "majority_vote",
                            "reasoning": "Stabilized by majority vote"
                        })
                    frame["allTechniques"] = filtered_techs

        return jsonify({
            "videoId": filename,
            "totalFrames": processed_count,
            "samplingFps": fps,
            "frames": frames_data
        })
    
    except Exception as e:
        app.logger.error(f"Error analyzing video: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/api/analyze-frame', methods=['POST'])
def analyze_frame():
    """
    Analyze single frame for pose detection
    
    Request:
        - frame: Image file (multipart/form-data)
    
    Response:
        {
          "keypoints": [...],
          "predictedPosition": "...",
          "confidence": 0.95
        }
    """
    try:
        if 'frame' not in request.files:
            return jsonify({"error": "No frame file provided"}), 400
        
        frame_file = request.files['frame']
        
        # Read image
        file_bytes = np.frombuffer(frame_file.read(), np.uint8)
        frame = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        
        # Load model and run inference
        yolo_model = load_model()
        results = yolo_model(frame, verbose=False)
        
        # Extract keypoints
        frame_data = extract_keypoints_from_result(results[0], 1, 0.0)
        
        return jsonify(frame_data), 200
        
    except Exception as e:
        app.logger.error(f"Error processing frame: {str(e)}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Development server
    port = int(os.getenv('PORT', 8081))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    app.logger.info(f"Starting YOLOv8 BJJ Pose Detection Service on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
