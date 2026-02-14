package com.bjj.videorec.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonAlias;
import lombok.Data;

/**
 * DTO representing a detected BJJ technique or position from AI analysis.
 * Provider-agnostic: works with any AI model (Gemini, OpenAI, etc.)
 */
@Data
public class TechniqueDetection {
    private Integer frameIndex; // Legacy support

    @JsonProperty("timestamp_seconds")
    @JsonAlias({ "timestamp", "sec" })
    private Double timestampSeconds;

    @JsonProperty("time")
    private String time; // Format "00:00"

    @JsonProperty("category")
    @JsonAlias({ "type", "kind" })
    private String type; // position, submission, sweep, pass, transition

    @JsonProperty("label")
    @JsonAlias({ "name", "technique" })
    private String name; // Technique name

    private String status; // Attempted | Secured | Completed
    private Double confidence; // 0.0 - 1.0

    @JsonProperty("detail")
    @JsonAlias({ "reasoning", "description", "details" })
    private String reasoning; // Chain of thought explanation

    @JsonProperty("observed_mechanics")
    private java.util.List<String> observedMechanics;

    @JsonProperty("potential_techniques")
    private java.util.List<String> potentialTechniques;

    @JsonProperty("geometric_evidence")
    private GeometricEvidence geometricEvidence;

    private String description; // Optional explanation

    /**
     * Nested class for geometric analysis evidence
     */
    @Data
    public static class GeometricEvidence {
        @JsonProperty("hip_angle")
        private Double hipAngle;

        @JsonProperty("elevation_diff")
        private String elevationDiff;

        @JsonProperty("key_vectors")
        private java.util.List<String> keyVectors;
    }
}
