package com.bjj.videorec.service;

import com.bjj.videorec.config.YoloV8Config;
import com.bjj.videorec.dto.PoseAnalysisResult;
import com.bjj.videorec.dto.PoseData;

import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.io.File;
import java.time.Duration;

/**
 * Service for communicating with YOLOv8 Python microservice
 * Handles HTTP requests for pose detection on videos and frames
 */
@Service

@Slf4j
public class YoloV8Service {

    private final YoloV8Config config;
    private final RestClient restClient;

    public YoloV8Service(YoloV8Config config) {
        this.config = config;
        this.restClient = RestClient.builder()
                .baseUrl(config.getUrl())
                .defaultHeaders(headers -> {
                    headers.setContentType(MediaType.MULTIPART_FORM_DATA);
                })
                .build();
    }

    /**
     * Analyze entire video for pose detection
     * 
     * @param videoFile Video file to analyze
     * @return PoseAnalysisResult with keypoints for each frame
     * @throws RuntimeException if service is disabled or request fails
     */
    public PoseAnalysisResult analyzeVideo(File videoFile) {
        if (!config.isEnabled()) {
            log.warn("YOLOv8 service is disabled, returning empty result");
            return createEmptyResult();
        }

        if (!videoFile.exists()) {
            throw new IllegalArgumentException("Video file does not exist: " + videoFile.getAbsolutePath());
        }

        log.info("Sending video to YOLOv8 service: {} ({} MB)",
                videoFile.getName(),
                videoFile.length() / (1024.0 * 1024.0));

        try {
            // Prepare multipart request
            MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
            body.add("video", new FileSystemResource(videoFile));
            body.add("fps", String.valueOf(config.getFps()));

            // Make HTTP request
            PoseAnalysisResult result = restClient.post()
                    .uri("/api/analyze-video")
                    .contentType(MediaType.MULTIPART_FORM_DATA)
                    .body(body)
                    .retrieve()
                    .body(PoseAnalysisResult.class);

            if (result == null) {
                log.error("YOLOv8 service returned null response");
                return createEmptyResult();
            }

            log.info("YOLOv8 analysis complete: {} frames processed", result.getTotalFrames());
            return result;

        } catch (RestClientException e) {
            log.error("Error calling YOLOv8 service: {}", e.getMessage(), e);
            throw new RuntimeException("YOLOv8 service request failed", e);
        }
    }

    /**
     * Analyze single frame for pose detection
     * 
     * @param frameFile Image file to analyze
     * @return PoseData with keypoints
     */
    public PoseData analyzeFrame(File frameFile) {
        if (!config.isEnabled()) {
            log.warn("YOLOv8 service is disabled");
            return new PoseData();
        }

        if (!frameFile.exists()) {
            throw new IllegalArgumentException("Frame file does not exist: " + frameFile.getAbsolutePath());
        }

        log.debug("Sending frame to YOLOv8 service: {}", frameFile.getName());

        try {
            MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
            body.add("frame", new FileSystemResource(frameFile));

            PoseData result = restClient.post()
                    .uri("/api/analyze-frame")
                    .contentType(MediaType.MULTIPART_FORM_DATA)
                    .body(body)
                    .retrieve()
                    .body(PoseData.class);

            return result != null ? result : new PoseData();

        } catch (RestClientException e) {
            log.error("Error analyzing frame: {}", e.getMessage(), e);
            return new PoseData();
        }
    }

    /**
     * Check if YOLOv8 service is healthy
     * 
     * @return true if service is responding, false otherwise
     */
    public boolean isHealthy() {
        if (!config.isEnabled()) {
            return false;
        }

        try {
            ResponseEntity<String> response = restClient.get()
                    .uri("/health")
                    .retrieve()
                    .toEntity(String.class);

            return response.getStatusCode().is2xxSuccessful();
        } catch (Exception e) {
            log.warn("YOLOv8 service health check failed: {}", e.getMessage());
            return false;
        }
    }

    /**
     * Create empty result for fallback scenarios
     */
    private PoseAnalysisResult createEmptyResult() {
        PoseAnalysisResult result = new PoseAnalysisResult();
        result.setTotalFrames(0);
        result.setFrames(java.util.Collections.emptyList());
        return result;
    }
}
