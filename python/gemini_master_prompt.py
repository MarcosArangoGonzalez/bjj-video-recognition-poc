"""
Gemini Master Prompt for BJJ Analysis
Integrates Roboflow BJJ-Positions model results with IBJJF scoring rules
"""

from typing import Dict, List, Any

class GeminiMasterPrompt:
    """
    Constructs IBJJF-compliant prompts for Gemini analysis
    Interprets Roboflow BJJ-Positions model outputs
    """
    
    # IBJJF Point System
    IBJJF_POINTS = {
        "takedown": 2,
        "knee_on_belly": 2,
        "sweep": 2,
        "guard_pass": 3,
        "mount": 4,
        "back_control": 4
    }
    
    # Position Hierarchy (IBJJF Classification)
    POSITION_HIERARCHY = {
        "dominant": ["mount", "back_control", "knee_on_belly"],
        "control": ["side_control", "north_south"],
        "neutral": ["standing", "turtle"],
        "defensive": ["closed_guard", "open_guard", "half_guard"]
    }
    
    # Submission Categories
    SUBMISSION_TYPES = {
        "chokes": ["rear_naked_choke", "guillotine", "triangle", "arm_triangle"],
        "joint_locks": ["armbar", "kimura", "americana", "omoplata"],
        "leg_attacks": ["heel_hook", "ankle_lock", "kneebar"]
    }
    
    @staticmethod
    def build_analysis_prompt(
        roboflow_detections: List[Dict[str, Any]],
        video_context: Dict[str, Any]
    ) -> str:
        """
        Build master prompt for Gemini incorporating Roboflow results
        
        Args:
            roboflow_detections: List of detections from BJJ-Positions model
                Example: [{"class": "armbar", "confidence": 0.87, "frame": 150}]
            video_context: Additional metadata (duration, fps, etc.)
        
        Returns:
            Structured prompt for Gemini with IBJJF context
        """
        
        prompt = f"""You are an IBJJF-certified BJJ referee and video analyst with expertise in technique recognition.

**ANALYSIS TASK:**
Analyze this Brazilian Jiu-Jitsu match video and generate accurate technique tags based on:
1. Roboflow BJJ-Positions model detections (pre-labeled frames)
2. Visual confirmation from the video
3. IBJJF competition rules and scoring system

**VIDEO METADATA:**
- Duration: {video_context.get('duration_seconds', 'N/A')} seconds
- FPS: {video_context.get('fps', 'N/A')}
- Total Frames: {video_context.get('total_frames', 'N/A')}

**ROBOFLOW MODEL DETECTIONS:**
The BJJ-Positions model (trained on 14,000+ images) has pre-labeled the following frames:

"""
        
        # Group detections by class
        detections_by_class = {}
        for det in roboflow_detections:
            cls = det.get('class', 'unknown')
            if cls not in detections_by_class:
                detections_by_class[cls] = []
            detections_by_class[cls].append(det)
        
        # Add detections to prompt
        for technique_class, detections in detections_by_class.items():
            avg_confidence = sum(d.get('confidence', 0) for d in detections) / len(detections)
            frame_numbers = [d.get('frame', 0) for d in detections]
            
            prompt += f"\n- **{technique_class.upper()}**:\n"
            prompt += f"  - Detected in {len(detections)} frames: {frame_numbers[:5]}{'...' if len(frame_numbers) > 5 else ''}\n"
            prompt += f"  - Average confidence: {avg_confidence:.1%}\n"
            
            # Add IBJJF context
            if technique_class in GeminiMasterPrompt.IBJJF_POINTS:
                points = GeminiMasterPrompt.IBJJF_POINTS[technique_class]
                prompt += f"  - IBJJF Points: {points}\n"
        
        # Add IBJJF Rules Context
        prompt += f"""

**IBJJF SCORING RULES TO APPLY:**

1. **Points System:**
{GeminiMasterPrompt._format_points_table()}

2. **Position Requirements:**
   - Positions must be held for **3 seconds** to score points
   - Back control requires at least one hook in
   - Mount requires dominant chest-to-chest control

3. **Submission Validation:**
   - Verify submission is legal for the belt level
   - Confirm opponent is in a defensive position (tapping or trapped)
   - Distinguish between submission attempts and successful finishes

**YOUR ANALYSIS INSTRUCTIONS:**

1. **Cross-Reference Detections:**
   - Review each Roboflow detection timestamp in the video
   - Confirm the technique is correctly identified
   - Check if position requirements (3-second rule) are met

2. **Score Transitions:**
   - Identify position changes that earn points (e.g., guard pass → side control)
   - Track who achieves each position first

3. **Submission Analysis:**
   - For detected submissions (armbar, triangle, RNC, etc.):
     * Verify mechanical execution (arm extended, triangle locked, etc.)
     * Confirm if it's a successful finish vs. attempt
     * Note the initiating position

4. **Output Format:**
   Return a JSON array of technique tags:
   ```json
   [
     {{
       "technique": "armbar",
       "timestamp_seconds": 45.2,
       "confidence": 0.92,
       "ibjjf_points": 0,
       "is_finish": true,
       "position_context": "mount",
       "athlete": "blue",
       "validation_notes": "Confirmed mechanical execution, opponent tapped"
     }},
     {{
       "technique": "sweep",
       "timestamp_seconds": 12.5,
       "confidence": 0.85,
       "ibjjf_points": 2,
       "is_finish": false,
       "position_context": "closed_guard",
       "athlete": "white",
       "validation_notes": "Clean sweep from closed guard, established top position for 3+ seconds"
     }}
   ]
   ```

5. **Validation Rules:**
   - If Roboflow confidence < 50%, manually verify from video before tagging
   - Reject detections that don't match IBJJF position definitions
   - Prioritize submissions over positions when simultaneous

**IMPORTANT:**
- Only tag techniques with **visual confirmation** in the video
- Apply strict IBJJF compliance (3-second rule, legal techniques only)
- For low-confidence Roboflow detections, increase scrutiny
"""
        
        return prompt
    
    @staticmethod
    def _format_points_table() -> str:
        """Format IBJJF points as a readable table"""
        lines = []
        for technique, points in GeminiMasterPrompt.IBJJF_POINTS.items():
            lines.append(f"   - {technique.replace('_', ' ').title()}: {points} points")
        return "\n".join(lines)
    
    @staticmethod
    def build_submission_confirmation_prompt(
        primary_detection: Dict[str, Any],
        video_clip_timestamp: float
    ) -> str:
        """
        Build specialized prompt for submission confirmation
        Used when primary model has low confidence (<50%)
        
        Args:
            primary_detection: Detection from BJJ-Positions model
            video_clip_timestamp: Timestamp to analyze
        
        Returns:
            Focused prompt for submission verification
        """
        
        technique = primary_detection.get('class', 'unknown')
        confidence = primary_detection.get('confidence', 0)
        
        prompt = f"""**SUBMISSION VERIFICATION TASK**

The primary BJJ-Positions model detected a **{technique.upper()}** at timestamp {video_clip_timestamp:.1f}s with {confidence:.1%} confidence.

This is BELOW the 50% threshold, requiring manual verification.

**VERIFICATION CHECKLIST FOR {technique.upper()}:**

"""
        
        # Add technique-specific mechanics
        if technique == "armbar":
            prompt += """
1. ✓ Opponent's arm is extended and isolated
2. ✓ Attacker's hips are positioned above the shoulder
3. ✓ Legs are controlling the opponent's head/neck
4. ✓ Opponent's thumb is pointing upward (proper rotation)
5. ✓ Clear submission finish (tap or ref stoppage)
"""
        elif technique == "triangle":
            prompt += """
1. ✓ Attacker's leg is across opponent's neck
2. ✓ Attacker's other leg is hooked behind the knee
3. ✓ Opponent's arm is trapped inside the triangle
4. ✓ Attacker is pulling opponent's head down
5. ✓ Clear submission finish (tap, unconscious, or ref stoppage)
"""
        elif technique == "rear_naked_choke":
            prompt += """
1. ✓ Attacker has back control with both hooks in
2. ✓ Attacker's arm is under opponent's chin (not across face)
3. ✓ Attacker's other hand is behind opponent's head
4. ✓ Opponent's posture is broken (chin tucked defense bypassed)
5. ✓ Clear submission finish (tap or unconsciousness)
"""
        
        prompt += f"""
**RESPOND WITH:**
```json
{{
  "is_valid_submission": true/false,
  "corrected_technique": "{technique} or alternative",
  "confidence_override": 0-100,
  "mechanical_validation": "describe what you see",
  "finish_confirmed": true/false
}}
```
"""
        
        return prompt


# Example Usage
if __name__ == '__main__':
    # Simulated Roboflow detections
    detections = [
        {"class": "armbar", "confidence": 0.87, "frame": 150, "bbox": [100, 200, 300, 400]},
        {"class": "mount", "confidence": 0.92, "frame": 120, "bbox": [150, 180, 320, 450]},
        {"class": "sweep", "confidence": 0.78, "frame": 45, "bbox": [200, 220, 340, 480]},
    ]
    
    video_context = {
        "duration_seconds": 180,
        "fps": 30,
        "total_frames": 5400
    }
    
    # Generate master prompt
    prompt = GeminiMasterPrompt.build_analysis_prompt(detections, video_context)
    
    print("="*80)
    print("GEMINI MASTER PROMPT")
    print("="*80)
    print(prompt)
    
    print("\n" + "="*80)
    print("SUBMISSION CONFIRMATION PROMPT")
    print("="*80)
    
    # Low-confidence detection requiring confirmation
    low_conf_detection = {"class": "triangle", "confidence": 0.42, "frame": 200}
    confirmation_prompt = GeminiMasterPrompt.build_submission_confirmation_prompt(
        low_conf_detection,
        6.67  # timestamp
    )
    print(confirmation_prompt)
