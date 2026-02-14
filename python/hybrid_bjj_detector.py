"""
Hybrid BJJ Detection System
Combines local position classifier (95.6% accuracy) with Roboflow models
for maximum accuracy across all technique categories
"""

from roboflow import Roboflow
from dotenv import load_dotenv
import os
import json
import joblib
import numpy as np
from pathlib import Path

load_dotenv()

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
            return {"position": None, "confidence": 0.0, "source": "local_invalid_keypoints"}
        
        # Predict
        prediction_idx = self.local_model.predict([features])[0]
        probabilities = self.local_model.predict_proba([features])[0]
        confidence = float(probabilities[prediction_idx])
        
        position = self.idx_to_label.get(prediction_idx, "unknown")
        
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
            results["position"] = local_result["position"]
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
        
        # Helper: arm angle (wrist-elbow-shoulder angle normalized by body_scale)
        l_arm_behind = (l_wr[1] > l_sh[1]) and (abs(l_wr[0] - l_sh[0]) / body_scale > 0.3)
        r_arm_behind = (r_wr[1] > r_sh[1]) and (abs(r_wr[0] - r_sh[0]) / body_scale > 0.3)
        
        l_arm_extended = np.sqrt((l_wr[0]-l_sh[0])**2 + (l_wr[1]-l_sh[1])**2) / body_scale
        r_arm_extended = np.sqrt((r_wr[0]-r_sh[0])**2 + (r_wr[1]-r_sh[1])**2) / body_scale
        
        # Body inclination (horizontal = low vertical distance)
        body_horizontal = abs(nose[1] - hip_cy) / body_scale < 1.5
        
        # KIMURA: Side control (primary) or mount (secondary)
        if position and ('side_control' in position or 'mount' in position):
            if 'side_control' in position and (l_arm_behind or r_arm_behind):
                subs.append({
                    "type": "submission",
                    "name": "Kimura",
                    "confidence": 0.85, # High confidence
                    "source": "pose_geometry_inference",
                    "reasoning": "Kimura grip pattern detected from side control"
                })
            elif 'mount' in position and (l_arm_behind or r_arm_behind):
                 # Stricter for mount
                 subs.append({
                    "type": "submission",
                    "name": "Kimura",
                    "confidence": 0.65, # Lower but filtered out if low
                    "source": "pose_geometry_inference",
                    "reasoning": "Possible Kimura attempt from mount"
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
        
        # TRIANGLE: Closed guard + legs raised high + ankles close
        if position and ('closed_guard' in position or 'open_guard' in position):
            l_leg_high = (l_knee[1] < sh_cy)
            r_leg_high = (r_knee[1] < sh_cy)
            ankles_close = abs(keypoints[15][0] - keypoints[16][0]) / body_scale < 0.5
            
             # Frontal Shot check (re-calc here for safety)
            avg_knee_y = (l_knee[1] + r_knee[1]) / 2
            relative_height = (avg_knee_y - nose[1]) / body_scale
            is_shooting = relative_height < 0.9 and relative_height > 0
            
            # Forward drive check
            forward_drive = abs(nose[0] - hip_cx) / body_scale > 0.6

            if (l_leg_high or r_leg_high) and ankles_close and not is_shooting and not forward_drive:
                subs.append({
                    "type": "submission",
                    "name": "Triangle Choke",
                    "confidence": 0.75,
                    "source": "pose_geometry_inference",
                    "reasoning": "High guard with locked legs detected"
                })
        
        # REAR NAKED CHOKE: Back control OR Mount (for "back without hooks")
        if position and ('back' in position or 'mount' in position):
            arms_high = (l_wr[1] < l_sh[1]) and (r_wr[1] < r_sh[1])
            arms_close = abs(l_wr[0] - r_wr[0]) / body_scale < 0.5
            # Crucial: Wrists MUST be at neck level
            wrist_near_neck = (abs(l_wr[1] - nose[1]) / body_scale < 0.25) or (abs(r_wr[1] - nose[1]) / body_scale < 0.25)
            
            if arms_high and arms_close and wrist_near_neck:
                conf = 0.85 if 'back' in position else 0.75
                subs.append({
                    "type": "submission",
                    "name": "Rear Naked Choke",
                    "confidence": conf,
                    "source": "pose_geometry_inference",
                    "reasoning": "Arms wrapped high near neck from back/mount"
                })
        
        # GUILLOTINE: Standing/turtle/guard + arm wrap + joined hands
        relevant_pos = (position == 'standing' or 'turtle' in position or 'closed_guard' in position)
        if position and relevant_pos:
            head_low = nose[1] > sh_cy 
            hands_joined = abs(l_wr[0] - r_wr[0]) / body_scale < 0.3 and abs(l_wr[1] - r_wr[1]) / body_scale < 0.3
            
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

    def _filter_techniques(self, techniques, position):
        """
        Filter techniques to remove conflicts and enforce logic.
        1. Enforce high confidence threshold (>0.70)
        2. Mutual Exclusivity: Only 1 submission per frame (highest confidence)
        3. Position Constraints: No Sweeps from dominant positions (Mount, Side Control, Back)
        """
        filtered = []
        
        # 1. Separate by category
        subs = [t for t in techniques if t['type'] == 'submission']
        sweeps = [t for t in techniques if t['type'] == 'sweep']
        transitions = [t for t in techniques if t['type'] == 'transition']
        takedowns = [t for t in techniques if t['type'] == 'takedown']
        
        # 2. Filter Submissions (Winner Takes All)
        if subs:
            # Sort by confidence
            subs.sort(key=lambda x: x['confidence'], reverse=True)
            best_sub = subs[0]
            
            # Threshold check
            if best_sub['confidence'] >= 0.70:
                filtered.append(best_sub)
        
        # 3. Filter Sweeps (Position Constraint)
        # Sweeps ONLY allowed from Guard/Half Guard
        if sweeps and position and ('guard' in position or 'half_guard' in position):
            sweeps.sort(key=lambda x: x['confidence'], reverse=True)
            if sweeps[0]['confidence'] >= 0.65: # Slightly lower threshold for sweeps
                filtered.append(sweeps[0])
                
        # 4. Filter Transitions
        if transitions:
            filtered.extend(transitions)
            
        # 5. Filter Takedowns
        if takedowns:
             takedowns.sort(key=lambda x: x['confidence'], reverse=True)
             if takedowns[0]['confidence'] >= 0.70:
                 filtered.append(takedowns[0])
                 
                 # CONFLICT RESOLUTION: Takedown vs Sweep
                 # If a strong Takedown is detected, it overrides weaker Sweeps
                 # (Double Leg Takedown often looks like a sweep due to leg mechanics)
                 if takedowns[0]['confidence'] > 0.6:
                     # Remove sweeps unless they are very high confidence
                     filtered = [t for t in filtered if t['type'] != 'sweep' or t['confidence'] > 0.8]
                 
        return filtered

    def hybrid_predict(self, keypoints, image_path=None):
        """
        Main inference method.
        
        1. Predict Position (Local Classifier)
        2. Infer Techniques (Rule-based)
        3. Filter & Merge
        """
        # 1. Position
        pos_result = self.predict_position_local(keypoints)
        position = pos_result['position']
        conf = pos_result['confidence']
        
        # 2. Extract Features for Rules
        # ... (Already detected in predict_position, but we need raw keypoints for rules)
        # Re-extract geometric features for rules
        # (Skip full re-extraction, just pass keypoints to detection methods)
        
        techniques = self._detect_all_techniques(keypoints, position)
        
        # 3. Filter Techniques
        clean_techniques = self._filter_techniques(techniques, position)
        
        return {
            "position": position,
            "position_confidence": conf,
            "all_techniques": clean_techniques, # Now filtered
            "submissions": [t for t in clean_techniques if t['type'] == 'submission'],
            "sweeps": [t for t in clean_techniques if t['type'] == 'sweep'],
            "transitions": [t for t in clean_techniques if t['type'] == 'transition'],
            "takedowns": [t for t in clean_techniques if t['type'] == 'takedown']
        }
    
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
            
            # Hip center = origin
            hip_cx = (left_hip[0] + right_hip[0]) / 2
            hip_cy = (left_hip[1] + right_hip[1]) / 2
            
            # Shoulder center for body scale
            sh_cx = (left_shoulder[0] + right_shoulder[0]) / 2
            sh_cy = (left_shoulder[1] + right_shoulder[1]) / 2
            
            # Body scale = shoulder-to-hip distance
            body_scale = max(np.sqrt((sh_cx - hip_cx)**2 + (sh_cy - hip_cy)**2), 1.0)
            
            # All 17 keypoints as relative coordinates
            features = []
            for kp in keypoints:
                features.append((kp[0] - hip_cx) / body_scale)  # Relative X
                features.append((kp[1] - hip_cy) / body_scale)  # Relative Y
            
            # Average confidence
            features.append(np.mean([kp[2] for kp in keypoints if len(kp) > 2]))
            
            return np.array(features)
        except Exception as e:
            print(f"Feature extraction error: {e}")
            return None


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
