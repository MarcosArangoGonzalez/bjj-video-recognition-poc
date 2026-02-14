package com.bjj.videorec.util;

/**
 * BJJ Expert Prompt V3 - Precision focused on Takedowns, Back Control and
 * Positional Hierarchy.
 */
public class BJJTechniquePrompt {

  /**
   * Prompt strategy enumeration
   */
  public enum PromptStrategy {
    BIOMECHANICAL, // Original CoT-based prompt
    GEOMETRIC, // New geometric/skeletal analysis prompt
    HYBRID // Combined geometric + biomechanical approach
  }

  private BJJTechniquePrompt() {
    throw new IllegalStateException("Utility class");
  }

  public static final String SYSTEM_PROMPT = """
      You are a specialized BJJ Analyst AI. Your goal is high-precision biomechanical analysis using Chain-of-Thought (CoT) reasoning.

      ### ANALYSIS PROTOCOL (Step-by-Step)
      1. **VISUAL SCAN**: Identify contact points (hands, feet, hips) and relative gravity (who is on top vs bottom).
      2. **HYPOTHESIS**: Based on mechanics, list 2-3 potential techniques (e.g., "Could be Triangle or High Guard").
      3. **VERIFICATION**: Apply biomechanical constraints (Truth Tables, Gravity Rule).
      4. **FINAL DECISION**: Select the most accurate classification.

      ### 1. VISUAL REASONING RULES (CoT)
      - **Describe before deciding**. Do not jump to "Guard" just because you see legs.
      - **Step 1 (Contact)**: "Hand on collar", "Leg acting as hook", "Chest pressure on face".
      - **Step 2 (Motion)**: "Hips elevating", "Shoulder rotation", "Passing the knee line".
      - **Step 3 (Space)**: "Is there space between chest and chest?" (If no -> Pin/Control).

      ### 2. FEW-SHOT VIDEO EXAMPLES (Reference Patterns)

      [PATTERN 1: THE "SIDE CONTROL" TRAP]
      **Observation**: Top player is perpendicular to bottom player (Chest-to-Chest). Bottom player's legs are flailing or trying to re-guard.
      **Common Error**: Labeling "Guard" because legs are visible.
      **Correct Logic**: "Chest is past the hips. Perpendicular angle. No legs between chests -> Side Control."

      [PATTERN 2: BACK CONTROL & RNC]
      **Observation**: Attacker is behind defender. One arm under chin.
      **Constraint Check**: "Are hooks (feet) inside the thighs?"
      **Correct Logic**: "Hooks in + Chest to Back -> Back Control (Secured). Arm under chin -> RNC."

      [PATTERN 3: TAKEDOWN vs PULLING GUARD]
      **Observation**: Match starts standing. Player A sits down and grabs a collar.
      **Correct Logic**: "Did Player B force them down? No. Player A sat down. -> Guard Pull (NOT Takedown)."

      [PATTERN 4: TAKEDOWN MECHANICS vs SUBMISSION]
      **Observation**: One player drives forward (standing). Legs entangle during the fall.
      **Common Error**: Labeling "Triangle Choke" because legs are around the neck.
      **Correct Logic**: "Forward momentum + Standing to Ground transition -> TAKEDOWN (not Submission). Triangles require stable guard."

      ### 3. POSITIONAL TRUTH TABLES (Constraints)
      - **Gravity Rule**: Top Player = Back/Hips NOT on mat. Bottom Player = Back/Side ON mat.
      - **Side Control**: Perpendicular + Chest-to-Chest + Past the legs.
      - **Mount**: Straddling the torso + Facing head.
      - **Back Control**: Behind torso + Hooks (feet) inside thighs.
      - **Mutual Exclusivity**: A Takedown (active motion) CANNOT happen with a Triangle Choke (static guard) at the same time. Priority: TAKEDOWN.
      - **Submission**: Only valid if the mechanic forces a tap (hyperextension or choke). "Attempt" if defending.

      ### 4. OUTPUT SCHEMA (Strict JSON)
      Return a JSON object with this EXACT structure for the sequence:
      {
        "sequence_summary": "Narrative summary of the fight mechanics.",
        "tags": [
          {
            "time": "MM:SS",
            "timestamp_seconds": 15.0,
            "category": "POSITION | SUBMISSION | TAKEDOWN | SWEEP | PASS",
            "label": "Techniques Name (e.g. 'Triangle Choke', 'Side Control')",
            "status": "Attempted | Secured | Completed",
            "observed_mechanics": ["List 2-3 visual cues", "e.g. Leg over shoulder", "Arm crossing centerline"],
            "potential_techniques": ["Hypothesis A", "Hypothesis B"],
            "detail": "Final reasoning based on verification. Why A and not B?",
            "confidence": 0.95
          }
        ]
      }
      """;

  /**
   * Build prompt using default biomechanical strategy
   */
  public static String buildPrompt() {
    return buildPrompt(PromptStrategy.HYBRID);
  }

  /**
   * Build prompt using specified strategy
   * 
   * @param strategy The prompting strategy to use
   * @return The constructed prompt
   */
  public static String buildPrompt(PromptStrategy strategy) {
    return switch (strategy) {
      case BIOMECHANICAL -> SYSTEM_PROMPT;
      case GEOMETRIC -> com.bjj.videorec.prompt.GeometricAnalysisPrompt.buildPrompt();
      case HYBRID -> com.bjj.videorec.prompt.HybridAnalysisPrompt.buildPrompt();
    };
  }

  /**
   * Build enhanced prompt that includes YOLOv8 pose data for context
   */
  public static String buildPromptWithPoseContext(com.bjj.videorec.dto.PoseAnalysisResult poseData) {
    StringBuilder prompt = new StringBuilder();
    prompt.append(buildPrompt(PromptStrategy.HYBRID));

    if (poseData != null && poseData.getFrames() != null && !poseData.getFrames().isEmpty()) {
      prompt.append("\n\n### TACTICAL VISION DATA (YOLOv8 Pose Extraction)\n");
      prompt.append(
          "You have access to pose keypoint data extracted by YOLOv8. Use this to validate your visual observations:\n\n");

      // Sample a few representative frames to include in prompt
      int sampleRate = Math.max(1, poseData.getFrames().size() / 10); // Sample ~10 frames
      prompt.append("Key frames with pose data:\n");

      for (int i = 0; i < poseData.getFrames().size(); i += sampleRate) {
        var frame = poseData.getFrames().get(i);
        prompt.append(String.format("\n- Frame %d (%.1fs): Position=%s, Confidence=%.2f, Keypoints=%d detected\n",
            frame.getFrameNumber(),
            frame.getTimestampSeconds(),
            frame.getPredictedPosition() != null ? frame.getPredictedPosition() : "unknown",
            frame.getConfidence(),
            frame.getKeypoints() != null ? frame.getKeypoints().size() : 0));
      }

      prompt.append("\nUse this pose data to:\n");
      prompt.append("1. Validate body positions (standing vs ground)\n");
      prompt.append("2. Identify center of gravity shifts\n");
      prompt.append("3. Detect contact points and leverage angles\n");
      prompt.append("4. Cross-reference your visual analysis with quantitative skeletal data\n");

      // Inject Hybrid Detector Results Summary (ALL frames)
      if (!poseData.getFrames().isEmpty()) {
        prompt.append("\n### LOCAL HYBRID DETECTOR FINDINGS (Frame-by-Frame Analysis)\n");
        prompt.append("The local rule-based system detected the following techniques throughout the video:\n");

        // Collect unique techniques to avoid spamming the prompt
        java.util.Set<String> uniqueTechs = new java.util.HashSet<>();
        java.util.List<String> summaryLines = new java.util.ArrayList<>();

        for (var frame : poseData.getFrames()) {
          if (frame.getAllTechniques() != null) {
            for (var tech : frame.getAllTechniques()) {
              if (tech != null && tech.getName() != null) {
                String key = tech.getName() + ":" + tech.getType();
                if (!uniqueTechs.contains(key)) {
                  uniqueTechs.add(key);
                  summaryLines.add(String.format("- %s (%.1fs): %s (Conf: %.2f) - %s",
                      tech.getType() != null ? tech.getType().toUpperCase() : "TECHNIQUE",
                      frame.getTimestampSeconds(),
                      tech.getName(),
                      tech.getConfidence(),
                      tech.getReasoning() != null ? tech.getReasoning() : ""));
                }
              }
            }
          }
        }

        if (!summaryLines.isEmpty()) {
          for (String line : summaryLines) {
            prompt.append(line).append("\n");
          }
          prompt.append(
              "\nIMPORTANT: Use these detections as high-confidence hints. If the local detector sees a submission, verify it visually.\n");
        } else {
          prompt.append("No specific techniques detected by local system (only basic positions).\n");
        }
      }
    }

    return prompt.toString();
  }
}