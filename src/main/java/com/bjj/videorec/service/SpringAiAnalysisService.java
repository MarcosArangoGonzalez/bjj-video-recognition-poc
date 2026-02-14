package com.bjj.videorec.service;

import com.bjj.videorec.dto.TechniqueDetection;
import com.bjj.videorec.dto.AnalysisResponse;
import com.bjj.videorec.dto.PoseAnalysisResult;
import com.bjj.videorec.util.BJJTechniquePrompt;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import com.fasterxml.jackson.core.type.TypeReference;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.core.io.FileSystemResource;
import org.springframework.stereotype.Service;
import org.springframework.util.MimeTypeUtils;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

/**
 * Implementation of AiAnalysisService using Spring AI ChatClient.
 */
@Service
@Slf4j
public class SpringAiAnalysisService implements AiAnalysisService {

    private final ChatClient chatClient;
    private final ObjectMapper objectMapper;

    public SpringAiAnalysisService(ChatClient.Builder chatClientBuilder, ObjectMapper objectMapper) {
        this.chatClient = chatClientBuilder.build();
        // Configure ObjectMapper to be more resilient
        this.objectMapper = objectMapper.copy()
                .configure(com.fasterxml.jackson.databind.DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
                .configure(com.fasterxml.jackson.databind.MapperFeature.ACCEPT_CASE_INSENSITIVE_PROPERTIES, true);
    }

    @Override
    public List<TechniqueDetection> analyzeFrames(List<File> frameFiles, List<Double> timestamps) {
        // ... (keeping parity but focus on analyzeVideo)
        if (frameFiles.isEmpty()) {
            return new ArrayList<>();
        }

        log.info(">>>> Analyzing batch of {} frames with Spring AI", frameFiles.size());

        try {
            String prompt = BJJTechniquePrompt.buildPrompt();

            var userSpec = chatClient.prompt().user(u -> {
                u.text(prompt);
                for (File frame : frameFiles) {
                    u.media(MimeTypeUtils.IMAGE_JPEG, new FileSystemResource(frame));
                }
            });

            String responseStr = userSpec.call().content();
            log.debug("Batch AI Response: {}", responseStr);
            return parseResponse(responseStr);

        } catch (Exception e) {
            log.error("CRITICAL ERROR calling AI provider for batch: {}", e.getMessage(), e);
            return new ArrayList<>();
        }
    }

    @Override
    public List<TechniqueDetection> analyzeVideo(File videoFile) {
        if (videoFile == null || !videoFile.exists()) {
            return new ArrayList<>();
        }

        log.info(">>>> Analyzing FULL VIDEO file: {} ({} bytes) with Spring AI",
                videoFile.getName(), videoFile.length());

        try {
            String prompt = BJJTechniquePrompt.buildPrompt();

            var userSpec = chatClient.prompt().user(u -> {
                u.text(prompt);
                // Dynamically determine MIME type or default to mp4
                String mimeType = "video/mp4";
                String filename = videoFile.getName().toLowerCase();
                if (filename.endsWith(".mov"))
                    mimeType = "video/quicktime";
                else if (filename.endsWith(".avi"))
                    mimeType = "video/x-msvideo";
                else if (filename.endsWith(".mpeg") || filename.endsWith(".mpg"))
                    mimeType = "video/mpeg";

                u.media(MimeTypeUtils.parseMimeType(mimeType), new FileSystemResource(videoFile));
            });

            String responseStr = userSpec.call().content();
            log.info(">>>> FULL VIDEO AI RESPONSE: {}", responseStr);

            if (responseStr == null || responseStr.isBlank()) {
                log.warn("!!!! Empty response from AI for video");
                return new ArrayList<>();
            }

            // Fix common Gemini formatting issues like trailing commas or missing quotes in
            // keys
            String sanitizedJson = sanitizeJson(responseStr);

            return parseResponse(sanitizedJson);

        } catch (Exception e) {
            Throwable root = e;
            while (root.getCause() != null)
                root = root.getCause();
            log.error("CRITICAL ERROR calling AI provider for video: {} | Root cause: {}",
                    e.getMessage(), root.getMessage(), e);
            return new ArrayList<>();
        }
    }

    private String sanitizeJson(String json) {
        if (json == null)
            return null;
        String clean = json.trim();
        // Remove markdown blocks
        if (clean.contains("```json")) {
            clean = clean.substring(clean.indexOf("```json") + 7);
            if (clean.contains("```")) {
                clean = clean.substring(0, clean.indexOf("```"));
            }
        } else if (clean.startsWith("```")) {
            clean = clean.substring(clean.indexOf("```") + 3);
            if (clean.contains("```")) {
                clean = clean.substring(0, clean.indexOf("```"));
            }
        }
        return clean.trim();
    }

    private List<TechniqueDetection> parseResponse(String rawResponse) {
        if (rawResponse == null || rawResponse.isBlank())
            return new ArrayList<>();

        try {
            AnalysisResponse response = objectMapper.readValue(rawResponse, AnalysisResponse.class);

            if (response != null && response.getDetections() != null) {
                return response.getDetections();
            }
        } catch (Exception e) {
            log.error("Failed to parse AI JSON response. Raw content was: {}", rawResponse, e);
            // Try emergency fallback parsing if it's a simple formatting error
            return tryHeuristicParse(rawResponse);
        }
        return new ArrayList<>();
    }

    private List<TechniqueDetection> tryHeuristicParse(String raw) {
        log.info("Attempting heuristic parse for failed JSON");

        try {
            // Strategy 1: Look for JSON Array [...]
            Pattern arrayPattern = Pattern.compile("\\[\\s*\\{.*\\}\\s*\\]", Pattern.DOTALL);
            Matcher arrayMatcher = arrayPattern.matcher(raw);
            if (arrayMatcher.find()) {
                String potentialJsonArray = arrayMatcher.group();
                log.debug("Found potential JSON array via regex");
                return objectMapper.readValue(potentialJsonArray, new TypeReference<List<TechniqueDetection>>() {
                });
            }

            // Strategy 2: Look for JSON Object {...} wrapping response
            Pattern objectPattern = Pattern.compile("\\{.*\\}", Pattern.DOTALL);
            Matcher objectMatcher = objectPattern.matcher(raw);
            if (objectMatcher.find()) {
                String potentialJsonObject = objectMatcher.group();
                log.debug("Found potential JSON object via regex");
                AnalysisResponse ar = objectMapper.readValue(potentialJsonObject, AnalysisResponse.class);
                if (ar != null && ar.getDetections() != null) {
                    return ar.getDetections();
                }
            }
        } catch (Exception e) {
            log.warn("Heuristic parse failed to recover valid data: {}", e.getMessage());
        }

        return new ArrayList<>();
    }

    @Override
    public List<TechniqueDetection> analyzeVideoWithPoses(File videoFile, PoseAnalysisResult poseData) {
        if (videoFile == null || !videoFile.exists()) {
            return new ArrayList<>();
        }

        log.info(">>>> Analyzing VIDEO with POSE CONTEXT: {} ({} bytes, {} pose frames)",
                videoFile.getName(), videoFile.length(),
                poseData != null ? poseData.getTotalFrames() : 0);

        try {
            // Build enhanced prompt with pose data using utility class
            String prompt = BJJTechniquePrompt.buildPromptWithPoseContext(poseData);

            var userSpec = chatClient.prompt().user(u -> {
                u.text(prompt);

                // Determine MIME type
                String mimeType = "video/mp4";
                String filename = videoFile.getName().toLowerCase();
                if (filename.endsWith(".mov"))
                    mimeType = "video/quicktime";
                else if (filename.endsWith(".avi"))
                    mimeType = "video/x-msvideo";
                else if (filename.endsWith(".mpeg") || filename.endsWith(".mpg"))
                    mimeType = "video/mpeg";

                u.media(MimeTypeUtils.parseMimeType(mimeType), new FileSystemResource(videoFile));
            });

            String responseStr = userSpec.call().content();
            log.info(">>>> VIDEO+POSE AI RESPONSE: {}", responseStr);

            if (responseStr == null || responseStr.isBlank()) {
                log.warn("!!!! Empty response from AI for video with poses");
                return new ArrayList<>();
            }

            String sanitizedJson = sanitizeJson(responseStr);
            List<TechniqueDetection> tags = parseResponse(sanitizedJson);
            return filterBiomechanicalHallucinations(tags);

        } catch (Exception e) {
            Throwable root = e;
            while (root.getCause() != null)
                root = root.getCause();
            log.error("CRITICAL ERROR calling AI provider for video with poses: {} | Root cause: {}",
                    e.getMessage(), root.getMessage(), e);
            return new ArrayList<>();
        }
    }

    private List<TechniqueDetection> filterBiomechanicalHallucinations(List<TechniqueDetection> tags) {
        if (tags == null || tags.isEmpty())
            return tags;

        List<TechniqueDetection> filtered = new ArrayList<>(tags);
        List<TechniqueDetection> toRemove = new ArrayList<>();

        // 1. Takedown vs Triangle Conflict
        boolean hasTakedown = tags.stream()
                .anyMatch(t -> t.getType() != null && t.getType().toUpperCase().contains("TAKEDOWN"));

        if (hasTakedown) {
            for (TechniqueDetection tag : filtered) {
                String name = (tag.getName() != null ? tag.getName() : "").toUpperCase();
                if (name.contains("TRIANGLE")) {
                    log.info("FILTERING: Removing '{}' because TAKEDOWN exists (hallucination prevention).",
                            tag.getName());
                    toRemove.add(tag);
                }
            }
        }

        // 2. S-Mount/Armbar vs Triangle Conflict
        boolean hasArmbarMount = tags.stream()
                .anyMatch(t -> (tagInfo(t)).contains("ARMBAR") && tagInfo(t).contains("MOUNT"));

        if (hasArmbarMount) {
            for (TechniqueDetection tag : filtered) {
                String info = tagInfo(tag);
                if (info.contains("TRIANGLE") && !info.contains("MOUNTED")) {
                    log.info("FILTERING: Removing '{}' because ARMBAR FROM MOUNT exists.", tag.getName());
                    toRemove.add(tag);
                }
            }
        }

        filtered.removeAll(toRemove);
        return filtered;
    }

    private String tagInfo(TechniqueDetection t) {
        return ((t.getName() != null ? t.getName() : "") + " " + (t.getReasoning() != null ? t.getReasoning() : ""))
                .toUpperCase();
    }
}
