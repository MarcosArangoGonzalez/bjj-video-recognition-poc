package com.bjj.videorec.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * Configuration properties for YOLOv8 Python service integration
 */
@Configuration
@ConfigurationProperties(prefix = "yolov8.service")
@Data
public class YoloV8Config {

    /**
     * URL of the YOLOv8 Python microservice
     * Default: http://localhost:8081
     */
    private String url = "http://localhost:8081";

    /**
     * Whether YOLOv8 service is enabled
     * If false, pose detection will be skipped
     */
    private boolean enabled = true;

    /**
     * HTTP request timeout in milliseconds
     * Default: 60 seconds
     */
    private int timeout = 60000;

    /**
     * Frames per second to extract from video
     * Higher = more detailed but slower/more expensive
     * Default: 1 FPS (one frame per second)
     */
    private int fps = 1;

    /**
     * Maximum video size in MB for processing
     */
    private int maxVideoSizeMb = 500;
}
