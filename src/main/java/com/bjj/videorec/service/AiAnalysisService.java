package com.bjj.videorec.service;

import com.bjj.videorec.dto.TechniqueDetection;
import java.io.File;
import java.io.IOException;
import java.util.List;

/**
 * Generic interface for AI-based video frame analysis
 */
public interface AiAnalysisService {
    /**
     * Analyze a batch of frames for BJJ techniques
     *
     * @param frameFiles List of image files to analyze
     * @param timestamps List of timestamps corresponding to the frames
     * @return List of detected techniques with frameIndex to map back to timestamps
     */
    List<TechniqueDetection> analyzeFrames(List<File> frameFiles, List<Double> timestamps) throws IOException;

    /**
     * Analyze full video file for BJJ techniques
     *
     * @param videoFile The video file (e.g., mp4)
     * @return List of detected techniques with accurate timestamps
     */
    List<TechniqueDetection> analyzeVideo(File videoFile);

    /**
     * Analyze video with enhanced pose context from YOLOv8
     * 
     * @param videoFile The video file to analyze
     * @param poseData  Pose keypoints extracted by YOLOv8
     * @return List of detected techniques with reasoning
     */
    List<TechniqueDetection> analyzeVideoWithPoses(File videoFile, com.bjj.videorec.dto.PoseAnalysisResult poseData);
}
