package com.bjj.videorec.dto;

import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

import java.util.List;
import java.util.Map;

/**
 * Complete pose analysis result from YOLOv8 service
 * Contains all frames analyzed from a video
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class PoseAnalysisResult {

    /**
     * Video identifier
     */
    private String videoId;

    /**
     * Total number of frames analyzed
     */
    private int totalFrames;

    /**
     * Original number of frames in video
     */
    private int originalFrames;

    /**
     * Frames per second used for sampling
     */
    private int fps;

    /**
     * List of pose data for each analyzed frame
     */
    private List<PoseData> frames;

    /**
     * Additional metadata (optional)
     */
    private Map<String, Object> metadata;
}
