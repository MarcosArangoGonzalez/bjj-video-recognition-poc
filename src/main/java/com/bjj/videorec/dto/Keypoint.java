package com.bjj.videorec.dto;

import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

/**
 * Individual keypoint data from YOLOv8 pose estimation
 * Represents one of the 17 COCO keypoints (nose, shoulders, elbows, etc.)
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class Keypoint {

    /**
     * Keypoint name (e.g., "nose", "left_shoulder", "right_knee")
     */
    private String name;

    /**
     * X coordinate in image space (pixels)
     */
    private double x;

    /**
     * Y coordinate in image space (pixels)
     */
    private double y;

    /**
     * Detection confidence (0.0 to 1.0)
     */
    private double confidence;
}
