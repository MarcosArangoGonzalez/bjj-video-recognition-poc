"""
Hybrid BJJ Detection System
Combines local position classifier (95.6% accuracy) with optional Roboflow models
for maximum accuracy across all technique categories.
"""

import os
import json
from pathlib import Path

import joblib
import numpy as np
from dotenv import load_dotenv
import logging

try:
    from roboflow import Roboflow
except Exception:
    Roboflow = None

load_dotenv()
logger = logging.getLogger(__name__)

class HybridBJJDetector:
    """
    Hybrid detection system optimizing for maximum accuracy
    
    Strategy:
    - Local Classifier: Positions (95.6% proven accuracy on 18 positions)
    - Roboflow BJJ-Positions: Submissions, Sweeps, Transitions, Takedowns
    - Confidence-based arbitration when both models detect same frame
    """
    
    # Technique categories
    POSITION_TECHNIQUES = [
        "mount", "mount1", "mount2",
        "back_control", "back1", "back2", 
        "side_control", "side_control1", "side_control2",
        "guard", "closed_guard", "closed_guard1", "closed_guard2",
        "open_guard", "open_guard1", "open_guard2",
        "half_guard", "half_guard1", "half_guard2",
        "5050_guard", "turtle", "turtle1", "turtle2",
        "standing"
    ]
    
    ROBOFLOW_PRIORITY_TECHNIQUES = [
        # Submissions (Roboflow has, local doesn't)
        "armbar", "triangle", "rear_naked_choke", 
        "guillotine", "kimura", "americana",
        # Sweeps (Roboflow has, local doesn't)
        "sweep", "butterfly_sweep", "scissor_sweep",
        # Transitions (Roboflow has, local doesn't)
        "guard_pass", "escape", "reversal"
    ]
    POSITION_CONFIDENCE_THRESHOLD = 0.50
    TECHNICAL_POSITION_THRESHOLD = 0.60
    NOISE_POSITION_PENALTIES = {
        "standing": 0.18,
        "scramble": 0.22,
    }
    NOISE_POSITION_LABELS = {"standing", "scramble", "unknown", "ground_position", "no_data"}
    MIN_REPORTABLE_TECHNIQUE_CONFIDENCE = 0.65
    SUBMISSION_HIERARCHY = {
        "triangle choke": 4,
        "armbar from mount": 3,
        "armbar": 3,
        "kimura": 2,
        "americana": 1,
    }
    
    def __init__(self, local_model_path="models/bjj_pose_classifier.pkl",
                 label_mapping_path="models/label_mapping.json",
                 api_key=None):
        """
        Initialize hybrid detector
        
        Args:
            local_model_path: Path to trained local position classifier
            label_mapping_path: Path to label mapping JSON
            api_key: Roboflow API key (optional, reads from env)
        """
        self.api_key = api_key or os.getenv('ROBOFLOW_API_KEY')
        
        # Load local position classifier
        self.local_model = None
        self.label_mapping = None
        self._load_local_model(local_model_path, label_mapping_path)
        
        # Initialize Roboflow models
        self.roboflow_models = {}
        self._init_roboflow_models()
        self.reset_sequence_state()

    def reset_sequence_state(self):
        self._position_history_instance = []
        self._stable_position = None
        self._pending_position = None
        self._pending_position_count = 0
        self.last_stable_position = None
        self.position_frames_count = 0
        self._last_hip_height = None
    
    def _load_local_model(self, model_path, mapping_path):
        """Load local trained classifier"""
        if Path(model_path).exists() and Path(mapping_path).exists():
            print(f"Loading local position classifier from {model_path}...")
            loaded = joblib.load(model_path)
            
            # Handle both formats: raw model or dict with 'model' key
            if isinstance(loaded, dict) and 'model' in loaded:
                print(f"  PKL contains dict with keys: {list(loaded.keys())}")
                self.local_model = loaded['model']
                # Use embedded label_mapping if available, fallback to JSON file
                if 'label_mapping' in loaded:
                    self.label_mapping = loaded['label_mapping']
                    print(f"  Using embedded label_mapping from PKL")
                else:
                    with open(mapping_path, 'r') as f:
                        self.label_mapping = json.load(f)
            else:
                self.local_model = loaded
                with open(mapping_path, 'r') as f:
                    self.label_mapping = json.load(f)
            
            # Reverse mapping (index -> label)
            self.idx_to_label = {v: k for k, v in self.label_mapping.items()}
            
            print(f"✓ Local classifier loaded: {len(self.label_mapping)} positions")
            print(f"  Model type: {type(self.local_model).__name__}")
        else:
            print(f"⚠ Local model not found at {model_path}")
            print("  Run: python train_bjj_classifier.py --annotations annotations.json")
    
    def _init_roboflow_models(self):
        """Initialize Roboflow models for non-position techniques"""
        if Roboflow is None:
            print("⚠ roboflow package not installed, Roboflow models disabled")
            return

        if not self.api_key:
            print("⚠ ROBOFLOW_API_KEY not set, Roboflow models disabled")
            return
        
        print("Initializing Roboflow BJJ-Positions model...")
        try:
            rf = Roboflow(api_key=self.api_key)
            project = rf.workspace("bjj-885sh").project("bjj-positions-eexsh")
            version = project.version(2)
            
            # Store the model object directly for prediction
            self.roboflow_models["bjj_positions"] = {
                "model": version.model,
                "project": "bjj-positions-eexsh",
                "description": "Submissions, Sweeps, Takedowns"
            }
            
            print(f"✓ Roboflow BJJ-Positions model loaded (type: {type(version.model)})")
        except Exception as e:
            print(f"⚠ Failed to load Roboflow model: {e}")
    
    def predict_position_local(self, keypoints):
        """
        Predict position using local classifier
        
        Args:
            keypoints: List of 17 COCO keypoints with [x, y, confidence]
        
        Returns:
            dict: {"position": str, "confidence": float}
        """
        if not self.local_model:
            return {"position": None, "confidence": 0.0, "source": "local_unavailable"}
        
        # Extract features (same as training)
        features = self._extract_features_from_keypoints(keypoints)
        if features is None:
            return {"position": "NO_DATA", "confidence": 0.0, "source": "local_invalid_keypoints"}
        
        # Predict
        probabilities = self.local_model.predict_proba([features])[0]
        scored_candidates = []
        best_technical = None

        for idx, probability in enumerate(probabilities):
            label = self.idx_to_label.get(idx, "unknown")
            normalized = self._normalize_position_label(label)
            raw_confidence = float(probability)
            scored_candidates.append(
                (
                    raw_confidence - self.NOISE_POSITION_PENALTIES.get(normalized, 0.0),
                    raw_confidence,
                    label,
                    normalized,
                )
            )
            if (
                normalized not in self.NOISE_POSITION_LABELS
                and raw_confidence >= self.TECHNICAL_POSITION_THRESHOLD
                and (best_technical is None or raw_confidence > best_technical[0])
            ):
                best_technical = (raw_confidence, label, normalized)

        _, confidence, position, normalized_position = max(scored_candidates, key=lambda item: item[0])
        if normalized_position in {"standing", "scramble"} and best_technical is not None:
            confidence, position, normalized_position = best_technical

        if confidence < self.POSITION_CONFIDENCE_THRESHOLD:
            return {"position": "unknown", "confidence": confidence, "source": "local_low_confidence"}
        
        return {
            "position": position,
            "confidence": confidence,
            "source": "local_classifier",
            "model_accuracy": 0.956  # Proven on test set
        }
    
    def predict_techniques_roboflow(self, image_path, confidence_threshold=40):
        """
        Predict techniques using Roboflow (submissions, sweeps, transitions)
        
        Args:
            image_path: Path to frame image
            confidence_threshold: Minimum confidence (0-100)
        
        Returns:
            list: [{"technique": str, "confidence": float, "bbox": [...]}]
        """
        if "bjj_positions" not in self.roboflow_models:
            return []
        
        try:
            rf_model = self.roboflow_models["bjj_positions"]["model"]
            
            # Run inference using the model directly
            predictions = rf_model.predict(image_path, confidence=confidence_threshold)
            results = predictions.json()
            
            # Filter for non-position techniques (submissions, sweeps, transitions)
            filtered_predictions = []
            for pred in results.get("predictions", []):
                technique = pred.get("class", "").lower()
                
                # Prioritize Roboflow for techniques not in local model
                if technique in self.ROBOFLOW_PRIORITY_TECHNIQUES or technique not in self.POSITION_TECHNIQUES:
                    filtered_predictions.append({
                        "technique": technique,
                        "confidence": pred.get("confidence", 0),
                        "bbox": [pred.get("x", 0), pred.get("y", 0), 
                                pred.get("width", 0), pred.get("height", 0)],
                        "source": "roboflow_bjj_positions"
                    })
            
            return filtered_predictions
            
        except Exception as e:
            print(f"Roboflow prediction error: {e}")
            return []
    
    def hybrid_predict(self, keypoints, image_path=None):
        """
        Hybrid prediction combining local classifier with rule-based technique inference.
        
        Strategy:
        1. Local classifier for positions (95.6% accuracy)
        2. Rule-based inference for submissions, sweeps, takedowns
        3. Temporal tracking for transitions
        
        Args:
            keypoints: COCO pose keypoints [[x, y, conf], ...]
            image_path: Path to frame image (for future use)
        
        Returns:
            dict: Complete analysis with all detected techniques
        """
        results = {
            "position": None,
            "position_confidence": 0.0,
            "submissions": [],
            "sweeps": [],
            "transitions": [],
            "takedowns": [],
            "all_techniques": []
        }
        
        # 1. Get position from local classifier (highest accuracy)
        local_result = self.predict_position_local(keypoints)
        if local_result["position"]:
            anchored_position = self._apply_position_anchor(local_result["position"], local_result["confidence"], keypoints)
            stable_position = self._apply_position_hysteresis(anchored_position)
            results["position"] = stable_position
            results["position_confidence"] = local_result["confidence"]
        
        # 2. Rule-based technique inference from keypoints + position
        if keypoints and len(keypoints) >= 17:
            inferred = self._infer_techniques_from_pose(keypoints, results["position"])
            
            for tech in inferred:
                category = tech["type"]
                if category == "submission":
                    results["submissions"].append(tech)
                elif category == "sweep":
                    results["sweeps"].append(tech)
                elif category == "transition":
                    results["transitions"].append(tech)
                elif category == "takedown":
                    results["takedowns"].append(tech)
                
                results["all_techniques"].append(tech)
        
        # 3. Track transitions (position changes over time)
        if results["position"]:
            transition = self._detect_transition(results["position"])
            if transition:
                results["transitions"].append(transition)
                results["all_techniques"].append(transition)
        
        return results

    def _apply_position_anchor(self, position, confidence, keypoints):
        position = self._normalize_position_label(position)
        if not position or not keypoints or len(keypoints) < 17:
            return position

        try:
            nose = keypoints[0]
            left_shoulder = keypoints[5]
            right_shoulder = keypoints[6]
            left_hip = keypoints[11]
            right_hip = keypoints[12]
            left_knee = keypoints[13]
            right_knee = keypoints[14]
            left_ankle = keypoints[15]
            right_ankle = keypoints[16]

            hip_cx = (left_hip[0] + right_hip[0]) / 2
            hip_cy = (left_hip[1] + right_hip[1]) / 2
            sh_cx = (left_shoulder[0] + right_shoulder[0]) / 2
            sh_cy = (left_shoulder[1] + right_shoulder[1]) / 2
            torso_height = max(np.sqrt((sh_cx - hip_cx) ** 2 + (sh_cy - hip_cy) ** 2), 1.0)

            head_high = (hip_cy - nose[1]) / torso_height > 1.15
            legs_down = min(left_knee[1], right_knee[1], left_ankle[1], right_ankle[1]) > hip_cy
            torso_vertical = abs(sh_cx - hip_cx) / torso_height < 0.45 and abs(sh_cy - hip_cy) / torso_height > 0.7
            s_mount_signature = self._detect_s_mount_signature(
                nose,
                left_knee,
                right_knee,
                left_ankle,
                right_ankle,
                hip_cx,
                hip_cy,
                torso_height,
            )
            armbar_activity = self._detect_armbar_activity(keypoints, torso_height)

            if s_mount_signature and ("50/50_guard" in position or "guard" in position or "mount" in position):
                return "mount"

            if self.last_stable_position in {"mount", "side_control"} and position == "50/50_guard":
                if confidence < 0.85:
                    logger.info("[Inertia] Rejected transition %s -> 50/50 due to low confidence %.2f", self.last_stable_position, confidence)
                    return self.last_stable_position
                if armbar_activity:
                    logger.info("[Inertia] Rejected transition Mount -> 50/50 due to Armbar activity")
                    return self.last_stable_position
                if not self._hip_height_inverted(hip_cy):
                    logger.info("[Inertia] Rejected transition %s -> 50/50 due to missing hip inversion", self.last_stable_position)
                    return self.last_stable_position

            if "back" in position:
                recent_window = self._position_history_instance[-4:] if hasattr(self, "_position_history_instance") else []
                if confidence < 0.70 and any("closed_guard" in item for item in recent_window):
                    return "closed_guard"
                if not torso_vertical or (head_high and legs_down):
                    if legs_down:
                        return "closed_guard"
                    return "standing"
        except Exception:
            return position
        return position

    def _apply_position_hysteresis(self, position):
        if not position:
            return position
        if self._stable_position is None:
            self._stable_position = position
            self.last_stable_position = position
            self.position_frames_count = 1
            return position
        self._stable_position = position
        self._pending_position = None
        self._pending_position_count = 0
        self.last_stable_position = position
        self.position_frames_count = 1
        return self._stable_position

    def _detect_s_mount_signature(self, nose, l_knee, r_knee, l_ankle, r_ankle, hip_cx, hip_cy, torso_height):
        ankle_near_head = min(
            np.sqrt((l_ankle[0] - nose[0]) ** 2 + (l_ankle[1] - nose[1]) ** 2),
            np.sqrt((r_ankle[0] - nose[0]) ** 2 + (r_ankle[1] - nose[1]) ** 2),
        ) / torso_height < 1.15
        knee_near_hip = min(
            np.sqrt((l_knee[0] - hip_cx) ** 2 + (l_knee[1] - hip_cy) ** 2),
            np.sqrt((r_knee[0] - hip_cx) ** 2 + (r_knee[1] - hip_cy) ** 2),
        ) / torso_height < 0.9
        return ankle_near_head and knee_near_hip

    def _detect_armbar_activity(self, keypoints, torso_height):
        try:
            l_sh = keypoints[5]
            r_sh = keypoints[6]
            l_elb = keypoints[7]
            r_elb = keypoints[8]
            l_wr = keypoints[9]
            r_wr = keypoints[10]
            left_elbow_angle = self._joint_angle(l_sh, l_elb, l_wr)
            right_elbow_angle = self._joint_angle(r_sh, r_elb, r_wr)
            l_arm_extended = np.sqrt((l_wr[0]-l_sh[0])**2 + (l_wr[1]-l_sh[1])**2) / torso_height
            r_arm_extended = np.sqrt((r_wr[0]-r_sh[0])**2 + (r_wr[1]-r_sh[1])**2) / torso_height
            return (
                (left_elbow_angle is not None and left_elbow_angle > 160.0)
                or (right_elbow_angle is not None and right_elbow_angle > 160.0)
                or l_arm_extended > 1.4
                or r_arm_extended > 1.4
            )
        except Exception:
            return False

    def _hip_height_inverted(self, hip_cy):
        inverted = self._last_hip_height is not None and hip_cy > self._last_hip_height + 12.0
        self._last_hip_height = hip_cy
        return inverted
    
    def _infer_techniques_from_pose(self, keypoints, position):
        """
        Infer submissions, sweeps, and takedowns from keypoint geometry + position.
        
        Uses biomechanical analysis of arm angles, body inclination,
        and positional context to detect specific techniques.
        """
        techniques = []
        
        try:
            nose = keypoints[0]
            left_shoulder = keypoints[5]
            right_shoulder = keypoints[6]
            left_elbow = keypoints[7]
            right_elbow = keypoints[8]
            left_wrist = keypoints[9]
            right_wrist = keypoints[10]
            left_hip = keypoints[11]
            right_hip = keypoints[12]
            left_knee = keypoints[13]
            right_knee = keypoints[14]
            left_ankle = keypoints[15]
            right_ankle = keypoints[16]
            
            # Body scale for normalization
            hip_cx = (left_hip[0] + right_hip[0]) / 2
            hip_cy = (left_hip[1] + right_hip[1]) / 2
            sh_cx = (left_shoulder[0] + right_shoulder[0]) / 2
            sh_cy = (left_shoulder[1] + right_shoulder[1]) / 2
            body_scale = max(np.sqrt((sh_cx - hip_cx)**2 + (sh_cy - hip_cy)**2), 1.0)
            
            # -- SUBMISSION DETECTION --
            submissions = self._detect_submissions(
                keypoints, position, body_scale,
                nose, left_shoulder, right_shoulder, 
                left_elbow, right_elbow, left_wrist, right_wrist,
                left_hip, right_hip, left_knee, right_knee,
                hip_cx, hip_cy, sh_cx, sh_cy
            )
            techniques.extend(submissions)
            
            # -- TAKEDOWN DETECTION --
            takedowns = self._detect_takedowns(
                keypoints, position, body_scale,
                nose, left_shoulder, right_shoulder,
                left_hip, right_hip, left_knee, right_knee,
                hip_cx, hip_cy, sh_cx, sh_cy
            )
            techniques.extend(takedowns)
            
            # -- SWEEP INDICATORS --
            sweeps = self._detect_sweeps(
                keypoints, position, body_scale,
                left_knee, right_knee, left_hip, right_hip,
                hip_cx, hip_cy, sh_cx, sh_cy
            )
            techniques.extend(sweeps)
            
        except (IndexError, TypeError) as e:
            pass  # Incomplete keypoints, skip inference
        
        return techniques
    
    def _detect_submissions(self, keypoints, position, body_scale,
                            nose, l_sh, r_sh, l_elb, r_elb, l_wr, r_wr,
                            l_hip, r_hip, l_knee, r_knee,
                            hip_cx, hip_cy, sh_cx, sh_cy):
        """Detect submission attempts from arm/body geometry and position context."""
        subs = []
        left_elbow_angle = self._joint_angle(l_sh, l_elb, l_wr)
        right_elbow_angle = self._joint_angle(r_sh, r_elb, r_wr)
        
        # Helper: arm angle (wrist-elbow-shoulder angle normalized by body_scale)
        l_arm_behind = (l_wr[1] > l_sh[1]) and (abs(l_wr[0] - l_sh[0]) / body_scale > 0.3)
        r_arm_behind = (r_wr[1] > r_sh[1]) and (abs(r_wr[0] - r_sh[0]) / body_scale > 0.3)
        
        l_arm_extended = np.sqrt((l_wr[0]-l_sh[0])**2 + (l_wr[1]-l_sh[1])**2) / body_scale
        r_arm_extended = np.sqrt((r_wr[0]-r_sh[0])**2 + (r_wr[1]-r_sh[1])**2) / body_scale
        
        # Body inclination (horizontal = low vertical distance)
        body_horizontal = abs(nose[1] - hip_cy) / body_scale < 1.5
        
        # KIMURA: prioritize arm geometry even when base position is uncertain.
        kimura_geometry = (l_arm_behind or r_arm_behind) and body_horizontal
        if kimura_geometry:
            kimura_confidence = 0.74
            kimura_reasoning = "Kimura grip geometry detected despite uncertain base position"
            if position and 'side_control' in position:
                kimura_confidence = 0.85
                kimura_reasoning = "Kimura grip pattern detected from side control"
            elif position and ('mount' in position or 'half_guard' in position or 'guard' in position):
                kimura_confidence = 0.72
                kimura_reasoning = f"Kimura grip geometry detected from {position}"
            subs.append({
                "type": "submission",
                "name": "Kimura",
                "confidence": kimura_confidence,
                "source": "pose_geometry_inference",
                "reasoning": kimura_reasoning
            })
        
        # S-MOUNT / MOUNT ARMBAR vs TRIANGLE
        # If in Mount, prioritize Armbar over Triangle (S-Mount often looks like Triangle legs)
        if position and 'mount' in position:
             # Check for S-Mount leg configuration (one leg tucked under armpit, one over head)
             # Simplified: If legs are close to shoulders/head
             legs_high = (l_knee[1] < sh_cy) or (r_knee[1] < sh_cy)
             if legs_high:
                  subs.append({
                    "type": "submission",
                    "name": "Armbar from Mount",
                    "confidence": 0.70,
                    "source": "pose_geometry_inference",
                    "reasoning": "High leg position consistent with S-Mount Armbar"
                })
        
        # AMERICANA: Mount or side control + arm pushed to the side
        if position and ('mount' in position or 'side_control' in position):
            arm_lateral = max(l_arm_extended, r_arm_extended) > 1.2
            if arm_lateral and body_horizontal:
                subs.append({
                    "type": "submission",
                    "name": "Americana",
                    "confidence": 0.75,
                    "source": "pose_geometry_inference",
                    "reasoning": "Lateral arm extension from dominant position"
                })
        
        # ARMBAR: Guard/mount + one arm extended
        if position and ('guard' in position or 'mount' in position or 'back' in position):
            # Strict threshold - Relaxed slightly for higher recall
            if l_arm_extended > 1.4 or r_arm_extended > 1.4: # Lowered from 1.6
                subs.append({
                    "type": "submission",
                    "name": "Armbar",
                    "confidence": 0.80,
                    "source": "pose_geometry_inference",
                    "reasoning": "Extended arm leverage detected"
                })

        # HARD GEOMETRY OVERRIDE: a fully extended elbow is an armbar signal.
        if position and ('guard' in position or 'mount' in position or 'back' in position or 'side_control' in position):
            if (left_elbow_angle is not None and left_elbow_angle > 160.0) or (
                right_elbow_angle is not None and right_elbow_angle > 160.0
            ):
                subs.append({
                    "type": "submission",
                    "name": "Armbar",
                    "confidence": 0.95,
                    "source": "pose_geometry_inference",
                    "reasoning": "Elbow angle above 160 degrees indicates armbar extension mechanics"
                })

        l_leg_high = (l_knee[1] < sh_cy)
        r_leg_high = (r_knee[1] < sh_cy)
        ankles_close = abs(keypoints[15][0] - keypoints[16][0]) / body_scale < 0.5
        ankle_to_neck = min(
            np.sqrt((keypoints[15][0] - nose[0]) ** 2 + (keypoints[15][1] - nose[1]) ** 2),
            np.sqrt((keypoints[16][0] - nose[0]) ** 2 + (keypoints[16][1] - nose[1]) ** 2),
        ) / body_scale
        avg_knee_y = (l_knee[1] + r_knee[1]) / 2
        relative_height = (avg_knee_y - nose[1]) / body_scale
        is_shooting = relative_height < 0.9 and relative_height > 0
        forward_drive = abs(nose[0] - hip_cx) / body_scale > 0.6
        head_low = nose[1] > sh_cy
        hands_joined = abs(l_wr[0] - r_wr[0]) / body_scale < 0.3 and abs(l_wr[1] - r_wr[1]) / body_scale < 0.3
        guard_submission_shape = ((l_leg_high or r_leg_high) and ankles_close and not is_shooting and not forward_drive) or (head_low and hands_joined)
        
        triangle_detected = False
        knees_above_hip = l_knee[1] < hip_cy and r_knee[1] < hip_cy
        if position and ('closed_guard' in position or 'open_guard' in position or 'half_guard' in position):
            if ankle_to_neck < 1.2 and knees_above_hip and not is_shooting and not forward_drive:
                triangle_detected = True
                subs.append({
                    "type": "submission",
                    "name": "Triangle Choke",
                    "confidence": 0.88,
                    "source": "pose_geometry_inference",
                    "reasoning": "Ankle-to-neck proximity with knees above hips indicates triangle closure"
                })
            elif (l_leg_high or r_leg_high) and ankles_close and not is_shooting and not forward_drive:
                triangle_detected = True
                subs.append({
                    "type": "submission",
                    "name": "Triangle Choke",
                    "confidence": 0.75,
                    "source": "pose_geometry_inference",
                    "reasoning": "High guard with locked legs detected"
                })
        
        # REAR NAKED CHOKE: Only from true back-control contexts.
        if position and 'back' in position:
            arms_high = (l_wr[1] < l_sh[1]) and (r_wr[1] < r_sh[1])
            arms_close = abs(l_wr[0] - r_wr[0]) / body_scale < 0.5
            # Crucial: Wrists MUST be at neck level
            wrist_near_neck = (abs(l_wr[1] - nose[1]) / body_scale < 0.25) or (abs(r_wr[1] - nose[1]) / body_scale < 0.25)
            
            if arms_high and arms_close and wrist_near_neck and not guard_submission_shape:
                subs.append({
                    "type": "submission",
                    "name": "Rear Naked Choke",
                    "confidence": 0.85,
                    "source": "pose_geometry_inference",
                    "reasoning": "Arms wrapped high near neck from back control"
                })
        
        # GUILLOTINE: Standing/turtle/guard + arm wrap + joined hands
        relevant_pos = (
            position == 'standing'
            or 'turtle' in position
            or 'closed_guard' in position
            or 'open_guard' in position
            or 'half_guard' in position
        )
        if position and relevant_pos and not triangle_detected:
            if head_low and hands_joined:
                subs.append({
                    "type": "submission",
                    "name": "Guillotine",
                    "confidence": 0.75,
                    "source": "pose_geometry_inference",
                    "reasoning": "Head-forward posture with clasped hands"
                })
        
        return subs
    
    def _detect_takedowns(self, keypoints, position, body_scale,
                         nose, l_sh, r_sh, l_hip, r_hip, l_knee, r_knee,
                         hip_cx, hip_cy, sh_cx, sh_cy):
        """Detect takedown attempts from body angles and position."""
        takedowns = []
        
        # Takedowns usually happen from standing or specific takedown positions
        if position and ('takedown' in position or position == 'standing'):
            # Level change: Shoulders dropping below hips (shooting)
            level_change = sh_cy > hip_cy 
            # Forward drive: Nose far ahead of hips (horizontal drive)
            forward_drive = abs(nose[0] - hip_cx) / body_scale > 0.6 # Lowered threshold
            
            # Frontal Shot / Level Change (Deep Squat)
            # Distance from nose to knees is small -> Head is low
            # Standard standing: ~1.5 to 2.0. Shooting: < 1.0
            avg_knee_y = (l_knee[1] + r_knee[1]) / 2
            relative_height = (avg_knee_y - nose[1]) / body_scale
            is_shooting = relative_height < 0.9 and relative_height > 0 # Head near knee level
            
            if 'takedown' in position:
                # Already classified as takedown by position classifier
                conf = 0.85
                takedowns.append({
                    "type": "takedown",
                    "name": "Takedown",
                    "confidence": conf,
                    "source": "position_classifier",
                    "reasoning": "Takedown position detected by classifier"
                })
                
                # Determine specific type
                if level_change:
                    takedowns.append({
                        "type": "takedown",
                        "name": "Double Leg Takedown",
                        "confidence": 0.65,
                        "source": "pose_geometry_inference",
                        "reasoning": "Level change (shoulders below hips) detected"
                    })
                elif forward_drive:
                     takedowns.append({
                        "type": "takedown",
                        "name": "Single Leg Takedown",
                        "confidence": 0.55, # Lowered to ensure candidate generation
                        "source": "pose_geometry_inference",
                        "reasoning": "Forward drive geometry detected"
                    })
                elif is_shooting:
                     takedowns.append({
                        "type": "takedown",
                        "name": "Takedown (Frontal)",
                        "confidence": 0.55,
                        "source": "pose_geometry_inference",
                        "reasoning": "Level change (shooting) detected from frontal view"
                    })
                    
            elif position == 'standing':
                 # Detect shot from standing
                 if level_change and (abs(l_knee[1] - r_knee[1]) / body_scale > 0.5):
                    # One knee down, shoulders low = Shooting
                    takedowns.append({
                        "type": "takedown",
                        "name": "Takedown Attempt",
                        "confidence": 0.55,
                        "source": "pose_geometry_inference",
                        "reasoning": "Shooting motion (level change + knee drop) from standing"
                    })
        
        return takedowns

    def _detect_sweeps(self, keypoints, position, body_scale,
                       l_knee, r_knee, l_hip, r_hip,
                       hip_cx, hip_cy, sh_cx, sh_cy):
        """Detect sweep attempts from guard positions."""
        sweeps = []
        
        if position and ('guard' in position or 'half_guard' in position):
            # Hip elevation: Hips significantly above shoulders (Bridge)
            hip_elevation = (sh_cy - hip_cy) / body_scale > 0.2
            
            # Legs driving/active: Knees close to hips (loaded) or splitting (scissor)
            legs_active = (l_knee[1] < l_hip[1] + body_scale*0.5) or (r_knee[1] < r_hip[1] + body_scale*0.5)
            
            # Anti-Takedown Check: Strong forward drive suggests Takedown, not Sweep
            # Forward drive calculation (same as in takedowns)
            nose = keypoints[0]
            forward_drive = abs(nose[0] - hip_cx) / body_scale > 0.6
            
            if hip_elevation and legs_active and not forward_drive:
                sweep_name = "Sweep"
                conf = 0.55
                reason = "Hip elevation and active legs detected"
                
                if 'half_guard' in position:
                    sweep_name = "Half Guard Sweep"
                    conf = 0.60
                    reason = "Bridge/roll motion from Half Guard"
                elif 'open_guard' in position:
                    # Butterfly check: Knees wide, feet close (simplified)
                    knees_wide = abs(l_knee[0] - r_knee[0]) / body_scale > 0.8
                    if knees_wide:
                        sweep_name = "Butterfly Sweep" 
                        conf = 0.55
                        reason = "Wide knee butterfly hook structure"
                elif 'closed_guard' in position:
                    # Scissor check: One leg high, one leg low/extended
                    leg_split = abs(l_knee[1] - r_knee[1]) / body_scale > 0.6
                    if leg_split:
                        sweep_name = "Scissor Sweep"
                        conf = 0.55
                        reason = "Leg split scissor mechanism"
                
                sweeps.append({
                    "type": "sweep",
                    "name": sweep_name,
                    "confidence": conf,
                    "source": "pose_geometry_inference",
                    "reasoning": reason
                })
        
        return sweeps
    
    # Frame history for transition detection
    _position_history = []
    
    def _detect_transition(self, current_position):
        """Detect transitions by tracking position changes over time."""
        if not hasattr(self, '_position_history_instance'):
            self._position_history_instance = []
        
        history = self._position_history_instance
        
        # Clean position name (remove trailing digits)
        import re
        clean_pos = re.sub(r'\d+$', '', current_position)
        
        transition = None
        
        if history and history[-1] != clean_pos:
            prev = history[-1]
            
            # Define valid transitions
            # Guard -> Mount
            if 'guard' in prev and 'mount' in clean_pos:
                transition = {
                    "type": "transition",
                    "name": "Sweep to Mount" if 'sweep' in str(history) else "Guard Pass to Mount",
                    "confidence": 0.85, # High confidence for position change
                    "source": "position_sequence",
                    "reasoning": f"Position changed from {prev} to {clean_pos}"
                }
            # Guard -> Side Control
            elif 'guard' in prev and 'side_control' in clean_pos:
                transition = {
                    "type": "transition",
                    "name": "Guard Pass to Side Control",
                    "confidence": 0.85,
                    "source": "position_sequence",
                    "reasoning": f"Position changed from {prev} to {clean_pos}"
                }
            # Side Control -> Mount
            elif 'side_control' in prev and 'mount' in clean_pos:
                transition = {
                    "type": "transition",
                    "name": "Mount Transition",
                    "confidence": 0.85,
                    "source": "position_sequence",
                    "reasoning": f"Position changed from {prev} to {clean_pos}"
                }
            # Side Control -> Back
            elif 'side_control' in prev and 'back' in clean_pos:
                transition = {
                    "type": "transition",
                    "name": "Back Take from Side Control",
                    "confidence": 0.85,
                    "source": "position_sequence",
                    "reasoning": f"Position changed from {prev} to {clean_pos}"
                }
            # Standing -> Takedown
            elif 'standing' in prev and 'takedown' in clean_pos:
                 transition = {
                    "type": "transition",
                    "name": "Takedown Entry",
                    "confidence": 0.85,
                    "source": "position_sequence",
                    "reasoning": f"Position changed from {prev} to {clean_pos}"
                }
        
        # Update history (keep last 10 frames)
        history.append(clean_pos)
        if len(history) > 10:
            history.pop(0)
        
        self._position_history_instance = history
        return transition

    @staticmethod
    def _joint_angle(a, b, c):
        try:
            if len(a) < 3 or len(b) < 3 or len(c) < 3:
                return None
            if a[2] < 0.1 or b[2] < 0.1 or c[2] < 0.1:
                return None
            ba = np.array([a[0] - b[0], a[1] - b[1]], dtype=float)
            bc = np.array([c[0] - b[0], c[1] - b[1]], dtype=float)
            denom = (np.linalg.norm(ba) * np.linalg.norm(bc)) + 1e-6
            cosine_angle = np.dot(ba, bc) / denom
            return float(np.degrees(np.arccos(np.clip(cosine_angle, -1.0, 1.0))))
        except Exception:
            return None

    def _filter_techniques(self, techniques, position):
        """
        Filter techniques to remove conflicts and enforce logic.
        1. Enforce high confidence threshold (>0.70)
        2. Mutual Exclusivity: Only 1 submission per frame (highest confidence)
        3. Position Constraints: No Sweeps from dominant positions (Mount, Side Control, Back)
        """
        filtered = []
        position = (position or "").lower()
        
        # 1. Separate by category
        subs = [t for t in techniques if t['type'] == 'submission']
        sweeps = [t for t in techniques if t['type'] == 'sweep']
        transitions = [t for t in techniques if t['type'] == 'transition']
        takedowns = [t for t in techniques if t['type'] == 'takedown']
        
        # 2. Filter Submissions (Winner Takes All)
        if subs:
            arm_submission_names = {"kimura", "armbar", "armbar from mount", "americana"}
            allowed_by_position = {
                "side_control": {"kimura", "americana"},
                "mount": {"armbar from mount", "armbar", "kimura", "americana"},
                "back": {"rear naked choke", "armbar"},
                "closed_guard": {"triangle choke", "guillotine", "armbar"},
                "open_guard": {"triangle choke", "guillotine", "armbar"},
                "half_guard": {"kimura", "guillotine", "armbar"},
                "turtle": {"guillotine", "lapel choke"},
                "standing": {"guillotine"},
            }

            allowed = next(
                (choices for key, choices in allowed_by_position.items() if key in position),
                None,
            )

            if any(
                str(item.get("name", "")).strip().lower() == "triangle choke"
                and float(item.get("confidence", 0.0) or 0.0) > 0.60
                for item in subs
            ):
                subs = [
                    item for item in subs
                    if str(item.get("name", "")).strip().lower() not in {"guillotine", "kimura"}
                ]

            def submission_score(item):
                confidence = item['confidence']
                normalized_name = str(item.get("name", "")).strip().lower()
                hierarchy = self.SUBMISSION_HIERARCHY.get(normalized_name, 0)
                if not allowed:
                    return (hierarchy * 10.0) + confidence
                if "side_control" in position and normalized_name == "kimura":
                    return (hierarchy * 10.0) + confidence + 0.22
                if normalized_name == "kimura" and confidence >= 0.72:
                    return (hierarchy * 10.0) + confidence + 0.08
                bonus = 0.18 if normalized_name in allowed else 0.0
                penalty = 0.18 if normalized_name not in allowed else 0.0
                return (hierarchy * 10.0) + confidence + bonus - penalty

            subs.sort(key=submission_score, reverse=True)
            best_sub = subs[0]
            
            # Threshold check
            if best_sub['confidence'] >= self.MIN_REPORTABLE_TECHNIQUE_CONFIDENCE:
                filtered.append(best_sub)
        
        # 3. Filter Sweeps (Position Constraint)
        # Sweeps ONLY allowed from Guard/Half Guard
        if sweeps and position and ('guard' in position or 'half_guard' in position):
            sweeps.sort(key=lambda x: x['confidence'], reverse=True)
            if sweeps[0]['confidence'] >= self.MIN_REPORTABLE_TECHNIQUE_CONFIDENCE:
                filtered.append(sweeps[0])
                
        # 4. Filter Transitions
        if transitions:
            transition_candidates = []
            for transition in transitions:
                name = str(transition.get("name", "")).strip().lower()
                if "guard pass" in name:
                    if not ("guard" in position and "side_control" in name):
                        continue
                transition_candidates.append(transition)
            if transition_candidates:
                transition_candidates.sort(key=lambda x: x['confidence'], reverse=True)
                filtered.append(transition_candidates[0])
            
        # 5. Filter Takedowns
        if takedowns:
             takedowns.sort(key=lambda x: x['confidence'], reverse=True)
             takedown_allowed = ('standing' in position or 'takedown' in position)
             if takedown_allowed and takedowns[0]['confidence'] >= self.MIN_REPORTABLE_TECHNIQUE_CONFIDENCE:
                 filtered.append(takedowns[0])
                 
                 # CONFLICT RESOLUTION: Takedown vs Sweep
                 # If a strong Takedown is detected, it overrides weaker Sweeps
                 # (Double Leg Takedown often looks like a sweep due to leg mechanics)
                 if takedowns[0]['confidence'] > 0.6:
                     # Remove sweeps unless they are very high confidence
                     filtered = [t for t in filtered if t['type'] != 'sweep' or t['confidence'] > 0.8]
                 
        return filtered

    # Mapping from Roboflow class names → internal {type, name} used by _filter_techniques
    _RF_TYPE_MAP = {
        "armbar":           ("submission", "Armbar"),
        "triangle":         ("submission", "Triangle Choke"),
        "rear_naked_choke": ("submission", "Rear Naked Choke"),
        "guillotine":       ("submission", "Guillotine"),
        "kimura":           ("submission", "Kimura"),
        "americana":        ("submission", "Americana"),
        "sweep":            ("sweep",      "Sweep"),
        "butterfly_sweep":  ("sweep",      "Butterfly Sweep"),
        "scissor_sweep":    ("sweep",      "Scissor Sweep"),
        "guard_pass":       ("transition", "Guard Pass"),
        "escape":           ("transition", "Escape"),
        "reversal":         ("transition", "Reversal"),
    }

    # Roboflow class name → canonical internal position label
    _RF_POSITION_MAP = {
        "side_control": "side_control2",
        "mount": "mount1",
        "back_control": "back1",
        "back": "back1",
        "closed_guard": "closed_guard1",
        "guard": "closed_guard1",
        "open_guard": "open_guard1",
        "half_guard": "half_guard1",
        "turtle": "turtle1",
        "standing": "standing",
        "50/50": "5050_guard",
        "5050": "5050_guard",
    }

    def hybrid_predict(self, keypoints, image_path=None):
        """
        Main inference method.

        1. Predict Position (Local Classifier)
        2. Rule-based technique inference from keypoint geometry
        3. Roboflow visual confirmation (only when image_path provided + API key set)
           3a. Position override when RF classifier confidence is low (< 0.5)
        4. Filter & Merge (Roboflow results override geometry when confidence is higher)
        5. Joint Angles
        """
        import logging as _log
        _logger = _log.getLogger(__name__)

        # 1. Position
        pos_result = self.predict_position_local(keypoints)
        position = pos_result['position']
        conf = pos_result['confidence']

        # 2. Rule-based geometry techniques
        techniques = self._detect_all_techniques(keypoints, position)

        # 3. Roboflow visual confirmation — only when image_path passed AND key is set
        if image_path and self.roboflow_models and "bjj_positions" in self.roboflow_models:
            try:
                rf_model = self.roboflow_models["bjj_positions"]["model"]
                rf_all = rf_model.predict(image_path, confidence=40).json().get("predictions", [])
            except Exception as _e:
                _logger.warning(f"Roboflow prediction error: {_e}")
                rf_all = []

            for pred in rf_all:
                cls = pred.get("class", "").lower()
                rf_conf = float(pred.get("confidence", 0.0))

                # 3a. Position override — when RF classifier has low confidence,
                #     trust Roboflow's visual position detection instead
                if conf < 0.5 and cls in self._RF_POSITION_MAP and rf_conf > conf:
                    new_pos = self._RF_POSITION_MAP[cls]
                    _logger.info(
                        f"[Roboflow] Position override: {position} (RF={conf:.2f}) "
                        f"→ {new_pos} (RF-visual={rf_conf:.2f})"
                    )
                    position = new_pos
                    conf = rf_conf

                # 3b. Technique confirmation (submissions / sweeps / transitions)
                tech_key = cls
                mapped = self._RF_TYPE_MAP.get(tech_key)
                if mapped:
                    t_type, t_name = mapped
                    techniques.append({
                        "type": t_type,
                        "name": t_name,
                        "confidence": rf_conf,
                        "source": "roboflow_bjj_positions",
                        "reasoning": f"Visual confirmation by Roboflow model (conf={rf_conf:.0%})",
                    })

        # 4. Filter & deduplicate (winner-takes-all per category, same thresholds)
        clean_techniques = self._filter_techniques(techniques, position)

        # 5. Joint Angles
        angles = self._calculate_joint_angles(keypoints)

        return {
            "position": position,
            "position_confidence": conf,
            "all_techniques": clean_techniques,
            "submissions": [t for t in clean_techniques if t['type'] == 'submission'],
            "sweeps":      [t for t in clean_techniques if t['type'] == 'sweep'],
            "transitions": [t for t in clean_techniques if t['type'] == 'transition'],
            "takedowns":   [t for t in clean_techniques if t['type'] == 'takedown'],
            "joint_angles": angles,
        }

    def _calculate_joint_angles(self, keypoints) -> dict:
        """Calculate biomechanical joint angles for cognitive validation."""
        if not keypoints or len(keypoints) < 17:
             return {}
             
        def get_angle(a, b, c):
            """Calculates the angle abc in degrees"""
            ba = np.array([a[0] - b[0], a[1] - b[1]])
            bc = np.array([c[0] - b[0], c[1] - b[1]])
            cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
            angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
            return np.degrees(angle)

        try:
            # keypoints are [[x,y,conf], ...]
            # Indices: 5:LSh, 7:LEl, 9:LWr, 6:RSh, 8:REl, 10:RWr, 11:LHip, 13:LKne, 15:LAnk, 12:RHip, 14:RKne, 16:RAnk
            angles = {
                "left_elbow_angle": get_angle(keypoints[5], keypoints[7], keypoints[9]),
                "right_elbow_angle": get_angle(keypoints[6], keypoints[8], keypoints[10]),
                "left_knee_angle": get_angle(keypoints[11], keypoints[13], keypoints[15]),
                "right_knee_angle": get_angle(keypoints[12], keypoints[14], keypoints[16]),
            }
            
            # Hip-Spine Angle (Approximation)
            sh_mid = [(keypoints[5][0] + keypoints[6][0])/2, (keypoints[5][1] + keypoints[6][1])/2]
            hip_mid = [(keypoints[11][0] + keypoints[12][0])/2, (keypoints[11][1] + keypoints[12][1])/2]
            # Use a point directly above hip for vertical reference
            vert_ref = [hip_mid[0], hip_mid[1] - 100]
            angles["spine_tilt_angle"] = get_angle(sh_mid, hip_mid, vert_ref)
            
            return {k: round(v, 2) for k, v in angles.items()}
        except Exception:
            return {}
    
    def _detect_all_techniques(self, keypoints, position):
        """Helper to run all detection rules raw"""
        # ... Keypoint extraction ...
        try:
             # Extract landmarks
            nose = keypoints[0]
            left_shoulder = keypoints[5]
            right_shoulder = keypoints[6]
            left_elbow = keypoints[7]
            right_elbow = keypoints[8]
            left_wrist = keypoints[9]
            right_wrist = keypoints[10]
            left_hip = keypoints[11]
            right_hip = keypoints[12]
            left_knee = keypoints[13]
            right_knee = keypoints[14]
            
            # Calculations
            hip_cx = (left_hip[0] + right_hip[0]) / 2
            hip_cy = (left_hip[1] + right_hip[1]) / 2
            sh_cx = (left_shoulder[0] + right_shoulder[0]) / 2
            sh_cy = (left_shoulder[1] + right_shoulder[1]) / 2
            body_scale = max(np.sqrt((sh_cx - hip_cx)**2 + (sh_cy - hip_cy)**2), 1.0)
            
            techniques = []
            
            # Submissions
            subs = self._detect_submissions(
                keypoints, position, body_scale,
                nose, left_shoulder, right_shoulder, left_elbow, right_elbow, left_wrist, right_wrist,
                left_hip, right_hip, left_knee, right_knee,
                hip_cx, hip_cy, sh_cx, sh_cy
            )
            techniques.extend(subs)
            
            # Takedowns
            takedowns = self._detect_takedowns(
                keypoints, position, body_scale,
                nose, left_shoulder, right_shoulder,
                left_hip, right_hip, left_knee, right_knee,
                hip_cx, hip_cy, sh_cx, sh_cy
            )
            techniques.extend(takedowns)
            
            # Sweeps
            sweeps = self._detect_sweeps(
                keypoints, position, body_scale,
                left_knee, right_knee, left_hip, right_hip,
                hip_cx, hip_cy, sh_cx, sh_cy
            )
            techniques.extend(sweeps)
            
            # Transitions
            trans = self._detect_transition(position)
            if trans:
                techniques.append(trans)
                
            return techniques
            
        except Exception as e:
            # print(f"Error in technique detection: {e}")
            return []
    
    def _extract_features_from_keypoints(self, keypoints):
        """
        Extract 35 RESOLUTION-INDEPENDENT features - MUST match training exactly!
        
        Features: All 17 COCO keypoints as (x,y) centered on hip midpoint
        and normalized by body_scale (shoulder-to-hip distance), plus avg confidence.
        
        Total: 17*2 + 1 = 35 features
        
        Keypoints: [[x, y, conf], ...] in COCO order (17 keypoints)
        """
        try:
            if not keypoints or len(keypoints) < 17:
                return None

            left_shoulder = keypoints[5]
            right_shoulder = keypoints[6]
            left_hip = keypoints[11]
            right_hip = keypoints[12]
            torso_confidences = [
                float(left_shoulder[2]) if len(left_shoulder) > 2 else 0.0,
                float(right_shoulder[2]) if len(right_shoulder) > 2 else 0.0,
                float(left_hip[2]) if len(left_hip) > 2 else 0.0,
                float(right_hip[2]) if len(right_hip) > 2 else 0.0,
            ]
            if min(torso_confidences) < 0.35:
                return None

            # Hip center = origin
            hip_cx = (left_hip[0] + right_hip[0]) / 2
            hip_cy = (left_hip[1] + right_hip[1]) / 2

            # Shoulder center for torso height scale
            sh_cx = (left_shoulder[0] + right_shoulder[0]) / 2
            sh_cy = (left_shoulder[1] + right_shoulder[1]) / 2

            # Torso height = shoulder-to-hip distance
            torso_height = max(np.sqrt((sh_cx - hip_cx)**2 + (sh_cy - hip_cy)**2), 1.0)

            # All 17 keypoints as relative coordinates
            features = []
            for kp in keypoints:
                features.append((kp[0] - hip_cx) / torso_height)  # Relative X
                features.append((kp[1] - hip_cy) / torso_height)  # Relative Y
            
            # Average confidence
            features.append(np.mean([kp[2] for kp in keypoints if len(kp) > 2]))
            
            return np.array(features)
        except Exception as e:
            print(f"Feature extraction error: {e}")
            return None

    @staticmethod
    def _normalize_position_label(label):
        normalized = str(label or "").strip().lower().replace(" ", "_")
        aliases = {
            "mount1": "mount",
            "mount2": "mount",
            "back1": "back",
            "back2": "back",
            "back_control": "back",
            "side_control1": "side_control",
            "side_control2": "side_control",
            "closed_guard1": "closed_guard",
            "closed_guard2": "closed_guard",
            "open_guard1": "open_guard",
            "open_guard2": "open_guard",
            "half_guard1": "half_guard",
            "half_guard2": "half_guard",
            "turtle1": "turtle",
            "turtle2": "turtle",
            "5050_guard": "50/50_guard",
        }
        return aliases.get(normalized, normalized)


# Example usage
if __name__ == '__main__':
    detector = HybridBJJDetector()
    
    print("\n" + "="*70)
    print("HYBRID BJJ DETECTOR INITIALIZED")
    print("="*70)
    print("\nAccuracy Optimization:")
    print("  ✓ Positions: Local Classifier (95.6% proven)")
    print("  ✓ Submissions: Roboflow BJJ-Positions (70-85% expected)")
    print("  ✓ Sweeps: Roboflow BJJ-Positions (65-80% expected)")
    print("  ✓ Transitions: Roboflow BJJ-Positions (60-75% expected)")
    print("  ✓ Takedowns: Roboflow BJJ-Positions (70-82% expected)")
    
    print("\n" + "="*70)
    print("USAGE EXAMPLE")
    print("="*70)
    print("""
# In YOLOv8 service:
from hybrid_bjj_detector import HybridBJJDetector

detector = HybridBJJDetector()

# Analyze frame
keypoints = yolo_pose_result['keypoints']  # From YOLOv8
image_path = 'frame_150.jpg'

results = detector.hybrid_predict(keypoints, image_path)

# Results contain:
# - position (from local classifier, 95.6% accuracy)
# - submissions (from Roboflow)
# - sweeps (from Roboflow)
# - transitions (from Roboflow)
    """)
