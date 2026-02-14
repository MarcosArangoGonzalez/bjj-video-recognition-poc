"""
Multi-Layer BJJ Detection Pipeline
Implements cascading detection system with three specialized models
"""

from roboflow import Roboflow
from dotenv import load_dotenv
import os
import json
from pathlib import Path

load_dotenv()

# Refined Model Configuration - BJJ-Positions as Master
MODELS = {
    "primary": {
        "workspace": "bjj-885sh",
        "project": "bjj-positions-eexsh",
        "version": 2,
        "description": "Master model (14k+ images): Submissions, Positions, Takedowns, Sweeps",
        "classes": [
            # Submissions
            "armbar", "triangle", "rear_naked_choke", "guillotine", 
            "kimura", "americana",
            # Positions
            "mount", "back_control", "side_control", 
            "guard", "half_guard", "closed_guard",
            # Techniques
            "takedown", "sweep"
        ],
        "priority": 1,
        "confidence_threshold": 40
    },
    
    "submission_specialist": {
        "workspace": "ana-beatriz-mdnhg",
        "project": "golpes-jiu-jitsu",
        "version": 1,
        "description": "Secondary specialist for submission confirmation",
        "classes": ["americana", "armlock", "triangle"],
        "priority": 2,
        "confidence_threshold": 60,
        "trigger_on_low_confidence": True  # Activate when primary < 50% on submissions
    }
}

# Submission trigger zones (positions that warrant submission detection)
SUBMISSION_TRIGGER_POSITIONS = [
    "mount", "mount1", "mount2",
    "back", "back1", "back2", "back_control",
    "side_control", "side_control1", "side_control2",
    "closed_guard", "closed_guard1", "closed_guard2",
    "triangle"  # Self-referential for triangle setups
]


class CascadingBJJDetector:
    """
    Three-layer cascading detection system for BJJ analysis
    
    Architecture:
    1. Scene Layer: Locate fighters on mat (bjj3)
    2. Position Layer: Classify BJJ position (rbflw-sample)
    3. Submission Layer: Detect submission technique (golpes-jiu-jitsu)
    """
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('ROBOFLOW_API_KEY')
        if not self.api_key:
            raise ValueError("ROBOFLOW_API_KEY required")
        
        self.rf = Roboflow(api_key=self.api_key)
        self.models = {}
        
    def load_models(self):
        """Load all three models from Roboflow"""
        print("Loading three-layer BJJ detection models...")
        
        for layer_name, config in MODELS.items():
            print(f"\nLayer: {layer_name.upper()}")
            print(f"  {config['description']}")
            
            try:
                project = self.rf.workspace(config["workspace"]).project(config["project"])
                version = project.version(config["version"])
                
                # Try to get hosted model or download for local inference
                self.models[layer_name] = {
                    "version": version,
                    "config": config,
                    "api_endpoint": f"https://detect.roboflow.com/{config['project']}/{config['version']}"
                }
                
                print(f"  ✓ Model loaded: {config['workspace']}/{config['project']}/v{config['version']}")
                
            except Exception as e:
                print(f"  ✗ Failed to load {layer_name}: {e}")
                self.models[layer_name] = None
        
        return self.models
    
    def analyze_frame(self, image_path, confidence_threshold=40):
        """
        Run cascading analysis on a single frame
        
        Args:
            image_path: Path to image file
            confidence_threshold: Minimum confidence (0-100)
        
        Returns:
            dict: Multi-layer prediction results
        """
        results = {
            "image": str(image_path),
            "layers": {}
        }
        
        # Layer 1: Scene Detection
        print(f"\n[Layer 1: Scene] Detecting fighters...")
        if self.models.get("scene"):
            try:
                scene_pred = self._predict_with_model("scene", image_path, confidence_threshold)
                results["layers"]["scene"] = scene_pred
                print(f"  Fighters detected: {len(scene_pred.get('predictions', []))}")
            except Exception as e:
                print(f"  Scene detection failed: {e}")
                results["layers"]["scene"] = None
        
        # Layer 2: Position Classification
        print(f"[Layer 2: Position] Analyzing BJJ position...")
        if self.models.get("position"):
            try:
                position_pred = self._predict_with_model("position", image_path, confidence_threshold)
                results["layers"]["position"] = position_pred
                
                # Extract top position
                top_position = self._get_top_prediction(position_pred)
                if top_position:
                    print(f"  Position detected: {top_position['class']} ({top_position['confidence']:.1%})")
                    results["detected_position"] = top_position["class"]
                else:
                    results["detected_position"] = None
                    
            except Exception as e:
                print(f"  Position detection failed: {e}")
                results["layers"]["position"] = None
                results["detected_position"] = None
        
        # Layer 3: Submission Detection (conditional)
        detected_position = results.get("detected_position", "")
        should_check_submission = any(
            trigger in detected_position.lower() 
            for trigger in SUBMISSION_TRIGGER_POSITIONS
        )
        
        if should_check_submission:
            print(f"[Layer 3: Submission] Danger zone detected, checking for submission...")
            if self.models.get("submission"):
                try:
                    submission_pred = self._predict_with_model("submission", image_path, confidence_threshold)
                    results["layers"]["submission"] = submission_pred
                    
                    top_submission = self._get_top_prediction(submission_pred)
                    if top_submission:
                        print(f"  ⚠️  SUBMISSION DETECTED: {top_submission['class']} ({top_submission['confidence']:.1%})")
                        results["detected_submission"] = top_submission["class"]
                    else:
                        results["detected_submission"] = None
                        
                except Exception as e:
                    print(f"  Submission detection failed: {e}")
                    results["layers"]["submission"] = None
        else:
            print(f"[Layer 3: Submission] Skipped (position '{detected_position}' not in danger zone)")
            results["layers"]["submission"] = "skipped"
        
        return results
    
    def _predict_with_model(self, layer_name, image_path, confidence):
        """Make prediction using Roboflow hosted API"""
        model_info = self.models[layer_name]
        
        # Use Roboflow's Python SDK prediction
        # Note: This uses hosted inference, not local model
        version = model_info["version"]
        
        # The version object should have a predict method
        # If not available, we'd need to use the HTTP API directly
        try:
            prediction = version.model.predict(image_path, confidence=confidence)
            return prediction.json()
        except AttributeError:
            # Fallback: model might not be available via API
            print(f"    Note: {layer_name} model inference not available (might require paid plan)")
            return {"predictions": [], "error": "API not available"}
    
    def _get_top_prediction(self, prediction_result):
        """Extract highest confidence prediction"""
        if not prediction_result or 'predictions' not in prediction_result:
            return None
        
        predictions = prediction_result['predictions']
        if not predictions:
            return None
        
        return max(predictions, key=lambda p: p.get('confidence', 0))


def demo_cascading_system(image_path):
    """Demonstrate the three-layer system on a single image"""
    print("="*70)
    print("MULTI-LAYER BJJ DETECTION DEMO")
    print("="*70)
    
    detector = CascadingBJJDetector()
    detector.load_models()
    
    results = detector.analyze_frame(image_path)
    
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    print(json.dumps(results, indent=2))
    
    return results


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Multi-layer BJJ detection system')
    parser.add_argument('--image', type=str, required=True,
                       help='Path to test image')
    parser.add_argument('--confidence', type=int, default=40,
                       help='Confidence threshold (0-100)')
    
    args = parser.parse_args()
    
    if not Path(args.image).exists():
        print(f"Error: Image not found: {args.image}")
        exit(1)
    
    demo_cascading_system(args.image)
