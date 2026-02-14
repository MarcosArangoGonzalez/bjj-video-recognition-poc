package com.bjj.videorec.dto;

import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

import java.util.List;

/**
 * Pose data for a single video frame
 * Contains keypoints, predicted BJJ position, and bounding boxes
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class PoseData {

    /**
     * Frame number (1-indexed)
     */
    private int frameNumber;

    /**
     * Timestamp in video (seconds)
     */
    private double timestampSeconds;

    /**
     * List of 17 COCO keypoints detected in this frame
     */
    private List<Keypoint> keypoints;

    /**
     * BJJ position predicted from keypoints
     * Examples: "standing", "guard", "mount", "side_control", "back_control"
     */
    private String predictedPosition;

    /**
     * Confidence of predicted position (0.0 to 1.0)
     * From local classifier (95.6% accuracy)
     */
    private Float positionConfidence;

    /**
     * Overall confidence of pose detection (0.0 to 1.0)
     */
    private double confidence;

    /**
     * Bounding boxes for detected persons (optional)
     */
    private List<BoundingBox> boundingBoxes;

    /**
     * Detected submissions from Roboflow (armbar, triangle, RNC, etc.)
     */
    private List<TechniqueInfo> detectedSubmissions;

    /**
     * Detected sweeps from Roboflow
     */
    private List<TechniqueInfo> detectedSweeps;

    /**
     * Detected transitions from Roboflow (guard pass, escape, reversal)
     */
    private List<TechniqueInfo> detectedTransitions;

    /**
     * All detected techniques (merged from all sources)
     */
    private List<TechniqueInfo> allTechniques;

    /**
     * Bounding box representation
     */
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class BoundingBox {
        private double x1;
        private double y1;
        private double x2;
        private double y2;
        private double confidence;
    }

    /**
     * Technique information from hybrid detector
     */
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class TechniqueInfo {
        private String type; // "position", "submission", "sweep", "transition"
        private String name;
        private double confidence;
        private String source; // "local_classifier_95.6%", "pose_geometry_inference", etc.
        private String reasoning; // Human-readable explanation of detection
    }
}
