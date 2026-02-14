package com.bjj.videorec.service;

import com.bjj.videorec.dto.TechniqueDetection;
import com.bjj.videorec.dto.PoseAnalysisResult;
import com.bjj.videorec.dto.PoseData;
import com.bjj.videorec.model.Video;
import com.bjj.videorec.model.VideoTag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.File;
import java.nio.file.Path;
import java.util.*;

@Service
@RequiredArgsConstructor
@Slf4j
public class BJJPoseDetectionService {

    private final AiAnalysisService aiAnalysisService;
    private final YoloV8Service yoloV8Service;

    @Value("${app.video.frames-per-second:1}")
    private int framesPerSecond;

    @Value("${yolov8.service.enabled:true}")
    private boolean yoloV8Enabled;

    /**
     * Analyze video for BJJ positions and techniques using TWO-STAGE PIPELINE:
     * Stage 1: YOLOv8 extracts pose keypoints (tactical vision)
     * Stage 2: Gemini reasons with video + pose context (cognitive layer)
     */
    public List<VideoTag> analyzeBJJPoses(Video video, Path videoPath) {
        List<VideoTag> tags = new ArrayList<>();

        try {
            File videoFile = videoPath.toFile();
            if (!videoFile.exists()) {
                log.error("Video file not found at path: {}", videoPath);
                return tags;
            }

            List<TechniqueDetection> detections;
            PoseAnalysisResult poseData = null;

            // Two-stage analysis if YOLOv8 is enabled
            if (yoloV8Enabled && yoloV8Service.isHealthy()) {
                log.info("Starting TWO-STAGE analysis (YOLOv8 + Gemini) for: {}", video.getFilename());

                // Stage 1: Extract pose keypoints + hybrid detection
                try {
                    poseData = yoloV8Service.analyzeVideo(videoFile);
                    log.info("YOLOv8 extracted poses from {} frames",
                            poseData != null ? poseData.getTotalFrames() : 0);
                } catch (Exception e) {
                    log.warn("YOLOv8 analysis failed, falling back to Gemini-only: {}", e.getMessage());
                }

                // Stage 2: Gemini analysis with pose context
                if (poseData != null && poseData.getTotalFrames() > 0) {
                    try {
                        detections = aiAnalysisService.analyzeVideoWithPoses(videoFile, poseData);

                        // !!!! FALLBACK: If Gemini fails OR returns zero detections, use hybrid
                        // detector results
                        if (detections.isEmpty()) {
                            log.warn(
                                    "Gemini returned zero detections - extracting techniques from YOLOv8 hybrid detector");
                            detections = extractTechniquesFromPoseData(poseData);
                        }
                    } catch (Exception geminiError) {
                        log.error("Gemini analysis failed: {} - Using YOLOv8 hybrid detector results as fallback",
                                geminiError.getMessage());
                        detections = extractTechniquesFromPoseData(poseData);
                    }
                } else {
                    log.info("No pose data available, using standard Gemini analysis");
                    detections = aiAnalysisService.analyzeVideo(videoFile);
                }
            } else {
                // Fallback: Direct Gemini analysis without pose data
                log.info("Starting GEMINI-ONLY analysis for: {} (YOLOv8 disabled or unavailable)",
                        video.getFilename());
                detections = aiAnalysisService.analyzeVideo(videoFile);
            }

            if (detections.isEmpty()) {
                log.warn("!!!! AI Analysis returned ZERO detections for video: {}", video.getFilename());
                // Fallback: If ZERO detections, log it clearly for debugging
            }

            for (TechniqueDetection detection : detections) {
                // Skip if essential fields are missing
                if (detection == null || detection.getName() == null || detection.getType() == null) {
                    continue;
                }

                // Thresholds - Adjusted to be more inclusive while maintaining quality
                // Since the new prompt doesn't include confidence, we default to 1.0 (pass)
                double confidence = detection.getConfidence() != null ? detection.getConfidence() : 0.95;
                double threshold = "POSITION".equalsIgnoreCase(detection.getType()) ? 0.15 : 0.50;

                if (confidence < threshold) {
                    log.info("#### Ignoring detection {} - Confidence {} below threshold {}",
                            detection.getName(), confidence, threshold);
                    continue;
                }

                VideoTag tag = new VideoTag();
                String tagName = formatTagName(detection.getType(), detection.getName());

                // Format: "CATEGORY: Name (Status): Explanation [Visuals: ...]"
                StringBuilder finalTagName = new StringBuilder(tagName);
                if (detection.getStatus() != null && !detection.getStatus().isBlank()) {
                    finalTagName.append(" (").append(detection.getStatus()).append(")");
                }

                // Add explanation with a ":" separator
                if (detection.getReasoning() != null && !detection.getReasoning().isBlank()) {
                    finalTagName.append(": ").append(detection.getReasoning());
                }

                // Add observed mechanics if strictly visual reasoning is used - requested
                // feature for CoT visibility
                if (detection.getObservedMechanics() != null && !detection.getObservedMechanics().isEmpty()) {
                    finalTagName.append(" [Visuals: ").append(String.join(", ", detection.getObservedMechanics()))
                            .append("]");
                }

                tag.setTagName(finalTagName.toString());
                tag.setConfidence((float) confidence);
                tag.setSource(VideoTag.TagSource.AUTO);

                // Use new "MM:SS" time if available, otherwise fallback to timestampSeconds
                float seconds = 0.0f;
                if (detection.getTime() != null) {
                    seconds = parseTimeStr(detection.getTime());
                } else if (detection.getTimestampSeconds() != null) {
                    seconds = detection.getTimestampSeconds().floatValue();
                }
                tag.setTimestampSeconds(seconds);

                tags.add(tag);

                log.info("Detected {}: {} [{}] (confidence: {}%, time: {}) - Detail: {}",
                        detection.getType(), detection.getName(),
                        detection.getStatus() != null ? detection.getStatus() : "N/A",
                        String.format("%.0f", tag.getConfidence() * 100),
                        detection.getTime() != null ? detection.getTime() : seconds + "s",
                        detection.getReasoning());
            }

            log.info("Native Gemini analysis completed: {} techniques detected", tags.size());

        } catch (Exception e) {
            log.error("Error running native Gemini BJJ analysis", e);
        }

        return tags;
    }

    private float parseTimeStr(String timeStr) {
        if (timeStr == null || !timeStr.contains(":"))
            return 0.0f;
        try {
            String[] parts = timeStr.trim().split(":");
            if (parts.length >= 2) {
                int mm = Integer.parseInt(parts[0]);
                int ss = Integer.parseInt(parts[1]);
                return (mm * 60) + ss;
            }
        } catch (Exception e) {
            log.warn("Failed to parse time string: {}", timeStr);
        }
        return 0.0f;
    }

    /**
     * Extract technique detections from YOLOv8 hybrid detector results
     * Used as fallback when Gemini analysis fails or returns zero detections
     */
    private List<TechniqueDetection> extractTechniquesFromPoseData(PoseAnalysisResult poseData) {
        List<TechniqueDetection> detections = new ArrayList<>();

        if (poseData == null || poseData.getFrames() == null) {
            return detections;
        }

        log.info("Extracting techniques from {} frames with hybrid detector results",
                poseData.getFrames().size());

        // Track unique techniques to avoid duplicates
        Map<String, TechniqueDetection> uniqueTechniques = new HashMap<>();

        for (com.bjj.videorec.dto.PoseData frame : poseData.getFrames()) {
            // Position detection from local classifier (95.6% accuracy)
            String position = frame.getPredictedPosition();
            Float positionConf = frame.getPositionConfidence();

            if (position != null && !position.equals("unknown") && !position.equals("ground_position")) {
                String key = "position_" + position;
                if (!uniqueTechniques.containsKey(key) ||
                        (positionConf != null && positionConf > uniqueTechniques.get(key).getConfidence())) {

                    TechniqueDetection detection = new TechniqueDetection();
                    // Clean: side_control1 -> Side Control
                    String cleanName = position.replaceAll("\\d+$", "").replace("_", " ").trim();
                    String[] words = cleanName.split(" ");
                    StringBuilder cap = new StringBuilder();
                    for (String w : words) {
                        if (!w.isEmpty()) {
                            if (cap.length() > 0)
                                cap.append(" ");
                            cap.append(w.substring(0, 1).toUpperCase()).append(w.substring(1));
                        }
                    }
                    detection.setName(cap.toString());
                    detection.setType("POSITION");
                    detection.setConfidence(positionConf != null ? (double) positionConf : 0.95);
                    detection.setTimestampSeconds(frame.getTimestampSeconds());
                    detection.setReasoning("Detected by local classifier (95.6% accuracy)");
                    detection.setStatus("detected");

                    uniqueTechniques.put(key, detection);
                }
            }

            // Extract submissions, sweeps, transitions, takedowns from allTechniques
            if (frame.getAllTechniques() != null) {
                for (PoseData.TechniqueInfo tech : frame.getAllTechniques()) {
                    if (tech == null || tech.getName() == null)
                        continue;

                    String techType = tech.getType() != null ? tech.getType().toUpperCase() : "TECHNIQUE";

                    // Skip position entries - already handled above with proper formatting
                    if ("POSITION".equals(techType))
                        continue;

                    String key = techType + "_" + tech.getName();

                    if (!uniqueTechniques.containsKey(key) ||
                            tech.getConfidence() > uniqueTechniques.get(key).getConfidence()) {

                        TechniqueDetection detection = new TechniqueDetection();
                        detection.setName(tech.getName());
                        detection.setType(techType);
                        detection.setConfidence(tech.getConfidence());
                        detection.setTimestampSeconds(frame.getTimestampSeconds());
                        String source = tech.getSource() != null ? tech.getSource() : "pose_analysis";
                        detection.setReasoning(
                                tech.getReasoning() != null ? tech.getReasoning() : "Detected by " + source);
                        detection.setStatus("detected");

                        uniqueTechniques.put(key, detection);
                    }
                }
            }
        }

        detections.addAll(uniqueTechniques.values());
        log.info("Extracted {} unique techniques from hybrid detector", detections.size());

        return detections;
    }

    /**
     * Format tag name based on detection type
     */
    private String formatTagName(String type, String name) {
        return switch (type.toUpperCase()) {
            case "POSITION" -> "POSITION: " + name;
            case "SUBMISSION" -> "SUBMISSION: " + name;
            case "SWEEP" -> "SWEEP: " + name;
            case "TAKEDOWN" -> "TAKEDOWN: " + name;
            case "TECHNIQUE" -> "TECH: " + name;
            case "TRANSITION" -> "TRANSITION: " + name;
            default -> name;
        };
    }
}
