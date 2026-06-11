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
import java.util.function.Function;

@Service
@Slf4j
public class SpringAiAnalysisService implements AiAnalysisService {

    private final List<ChatClient> chatClients;
    private final ObjectMapper objectMapper;

    public SpringAiAnalysisService(List<ChatClient> chatClients, ObjectMapper objectMapper) {
        this.chatClients = chatClients;
        this.objectMapper = objectMapper.copy()
                .configure(com.fasterxml.jackson.databind.DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
                .configure(com.fasterxml.jackson.databind.MapperFeature.ACCEPT_CASE_INSENSITIVE_PROPERTIES, true);
        log.info("SpringAiAnalysisService initialised with {} Gemini client(s)", chatClients.size());
    }

    private String callWithFallback(Function<ChatClient, String> fn) {
        Exception last = null;
        for (int i = 0; i < chatClients.size(); i++) {
            try {
                String result = fn.apply(chatClients.get(i));
                if (result != null && !result.isBlank()) {
                    if (i > 0) log.info("Key rotation: succeeded with client #{}", i + 1);
                    return result;
                }
            } catch (Exception e) {
                log.warn("ChatClient #{} failed (quota/error), trying next: {}", i + 1, e.getMessage());
                last = e;
            }
        }
        if (last != null) throw new RuntimeException("All Gemini keys exhausted", last);
        return "";
    }

    @Override
    public List<TechniqueDetection> analyzeFrames(List<File> frameFiles, List<Double> timestamps) {
        if (frameFiles.isEmpty()) {
            return new ArrayList<>();
        }

        log.info(">>>> Analyzing batch of {} frames with Spring AI", frameFiles.size());

        try {
            String prompt = BJJTechniquePrompt.buildPrompt();
            String responseStr = callWithFallback(client -> client.prompt().user(u -> {
                u.text(prompt);
                for (File frame : frameFiles) {
                    u.media(MimeTypeUtils.IMAGE_JPEG, new FileSystemResource(frame));
                }
            }).call().content());
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
            String mimeType = resolveMimeType(videoFile.getName());

            String responseStr = callWithFallback(client -> client.prompt().user(u -> {
                u.text(prompt);
                u.media(MimeTypeUtils.parseMimeType(mimeType), new FileSystemResource(videoFile));
            }).call().content());

            log.info(">>>> FULL VIDEO AI RESPONSE: {}", responseStr);

            if (responseStr == null || responseStr.isBlank()) {
                log.warn("!!!! Empty response from AI for video");
                return new ArrayList<>();
            }

            return parseResponse(sanitizeJson(responseStr));

        } catch (Exception e) {
            Throwable root = e;
            while (root.getCause() != null) root = root.getCause();
            log.error("CRITICAL ERROR calling AI provider for video: {} | Root cause: {}",
                    e.getMessage(), root.getMessage(), e);
            return new ArrayList<>();
        }
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
            String prompt = BJJTechniquePrompt.buildPromptWithPoseContext(poseData);
            String mimeType = resolveMimeType(videoFile.getName());

            String responseStr = callWithFallback(client -> client.prompt().user(u -> {
                u.text(prompt);
                u.media(MimeTypeUtils.parseMimeType(mimeType), new FileSystemResource(videoFile));
            }).call().content());

            log.info(">>>> VIDEO+POSE AI RESPONSE: {}", responseStr);

            if (responseStr == null || responseStr.isBlank()) {
                log.warn("!!!! Empty response from AI for video with poses");
                return new ArrayList<>();
            }

            List<TechniqueDetection> tags = parseResponse(sanitizeJson(responseStr));
            return filterBiomechanicalHallucinations(tags);

        } catch (Exception e) {
            Throwable root = e;
            while (root.getCause() != null) root = root.getCause();
            log.error("CRITICAL ERROR calling AI provider for video with poses: {} | Root cause: {}",
                    e.getMessage(), root.getMessage(), e);
            return new ArrayList<>();
        }
    }

    private String resolveMimeType(String filename) {
        String lower = filename.toLowerCase();
        if (lower.endsWith(".mov")) return "video/quicktime";
        if (lower.endsWith(".avi")) return "video/x-msvideo";
        if (lower.endsWith(".mpeg") || lower.endsWith(".mpg")) return "video/mpeg";
        return "video/mp4";
    }

    private String sanitizeJson(String json) {
        if (json == null) return null;
        String clean = json.trim();
        if (clean.contains("```json")) {
            clean = clean.substring(clean.indexOf("```json") + 7);
            if (clean.contains("```")) clean = clean.substring(0, clean.indexOf("```"));
        } else if (clean.startsWith("```")) {
            clean = clean.substring(clean.indexOf("```") + 3);
            if (clean.contains("```")) clean = clean.substring(0, clean.indexOf("```"));
        }
        return clean.trim();
    }

    private List<TechniqueDetection> parseResponse(String rawResponse) {
        if (rawResponse == null || rawResponse.isBlank()) return new ArrayList<>();
        try {
            AnalysisResponse response = objectMapper.readValue(rawResponse, AnalysisResponse.class);
            if (response != null && response.getDetections() != null) {
                return response.getDetections();
            }
        } catch (Exception e) {
            log.error("Failed to parse AI JSON response. Raw content was: {}", rawResponse, e);
            return tryHeuristicParse(rawResponse);
        }
        return new ArrayList<>();
    }

    private List<TechniqueDetection> tryHeuristicParse(String raw) {
        log.info("Attempting heuristic parse for failed JSON");
        try {
            Pattern arrayPattern = Pattern.compile("\\[\\s*\\{.*\\}\\s*\\]", Pattern.DOTALL);
            Matcher arrayMatcher = arrayPattern.matcher(raw);
            if (arrayMatcher.find()) {
                return objectMapper.readValue(arrayMatcher.group(), new TypeReference<List<TechniqueDetection>>() {});
            }
            Pattern objectPattern = Pattern.compile("\\{.*\\}", Pattern.DOTALL);
            Matcher objectMatcher = objectPattern.matcher(raw);
            if (objectMatcher.find()) {
                AnalysisResponse ar = objectMapper.readValue(objectMatcher.group(), AnalysisResponse.class);
                if (ar != null && ar.getDetections() != null) return ar.getDetections();
            }
        } catch (Exception e) {
            log.warn("Heuristic parse failed to recover valid data: {}", e.getMessage());
        }
        return new ArrayList<>();
    }

    private List<TechniqueDetection> filterBiomechanicalHallucinations(List<TechniqueDetection> tags) {
        if (tags == null || tags.isEmpty()) return tags;

        List<TechniqueDetection> filtered = new ArrayList<>(tags);
        List<TechniqueDetection> toRemove = new ArrayList<>();

        boolean hasTakedown = tags.stream()
                .anyMatch(t -> t.getType() != null && t.getType().toUpperCase().contains("TAKEDOWN"));
        if (hasTakedown) {
            for (TechniqueDetection tag : filtered) {
                if ((tag.getName() != null ? tag.getName() : "").toUpperCase().contains("TRIANGLE")) {
                    log.info("FILTERING: Removing '{}' because TAKEDOWN exists.", tag.getName());
                    toRemove.add(tag);
                }
            }
        }

        boolean hasArmbarMount = tags.stream()
                .anyMatch(t -> tagInfo(t).contains("ARMBAR") && tagInfo(t).contains("MOUNT"));
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
        return ((t.getName() != null ? t.getName() : "") + " " +
                (t.getReasoning() != null ? t.getReasoning() : "")).toUpperCase();
    }
}
