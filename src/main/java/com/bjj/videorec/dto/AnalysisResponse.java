package com.bjj.videorec.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonAlias;
import lombok.Data;
import java.util.List;

/**
 * DTO for AI analysis response wrapper.
 * Provider-agnostic: works with any AI model (Gemini, OpenAI, etc.)
 */
@Data
public class AnalysisResponse {
    @JsonProperty("summary")
    @JsonAlias("sequence_summary")
    private String sequenceSummary;
    
    @JsonProperty("tags")
    @JsonAlias("detections")
    private List<TechniqueDetection> detections;
}
