package com.bjj.videorec.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/**
 * Service for extracting frames from videos using FFmpeg
 */
@Service
@Slf4j
public class VideoFrameExtractor {

    @Value("${app.video.frames-per-second:1}")
    private int framesPerSecond;

    /**
     * Extract frames from video at specified intervals
     * 
     * @param videoPath Path to the video file
     * @return List of extracted frame files
     */
    public List<File> extractFrames(Path videoPath) throws IOException {
        // Create temporary directory for frames
        Path tempDir = Files.createTempDirectory("bjj-frames-");
        log.info("Extracting frames from {} to {}", videoPath, tempDir);

        // Build FFmpeg command
        // Extract N frames per second
        String outputPattern = tempDir.resolve("frame_%04d.jpg").toString();

        ProcessBuilder processBuilder = new ProcessBuilder(
                "ffmpeg",
                "-i", videoPath.toString(),
                "-vf", "fps=" + framesPerSecond, // N frames per second
                "-q:v", "2", // High quality JPEG
                outputPattern);

        processBuilder.redirectErrorStream(true);

        try {
            Process process = processBuilder.start();

            // Read output
            StringBuilder output = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    output.append(line).append("\n");
                }
            }

            int exitCode = process.waitFor();
            if (exitCode != 0) {
                log.error("FFmpeg failed with exit code: {}", exitCode);
                log.error("Output: {}", output);
                throw new IOException("FFmpeg frame extraction failed");
            }

            // Collect extracted frames
            File[] frameFiles = tempDir.toFile().listFiles((dir, name) -> name.endsWith(".jpg"));
            if (frameFiles == null || frameFiles.length == 0) {
                log.warn("No frames extracted from video");
                return new ArrayList<>();
            }

            List<File> frames = new ArrayList<>(List.of(frameFiles));
            frames.sort((a, b) -> a.getName().compareTo(b.getName()));

            log.info("Extracted {} frames from video", frames.size());
            return frames;

        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("Frame extraction interrupted", e);
        }
    }

    /**
     * Clean up temporary frame files
     */
    public void cleanupFrames(List<File> frames) {
        if (frames == null || frames.isEmpty()) {
            return;
        }

        // Get parent directory
        File parentDir = frames.get(0).getParentFile();

        // Delete all frames
        for (File frame : frames) {
            try {
                Files.deleteIfExists(frame.toPath());
            } catch (IOException e) {
                log.warn("Failed to delete frame: {}", frame.getName(), e);
            }
        }

        // Delete parent directory
        try {
            Files.deleteIfExists(parentDir.toPath());
            log.debug("Cleaned up frame directory: {}", parentDir);
        } catch (IOException e) {
            log.warn("Failed to delete frame directory: {}", parentDir, e);
        }
    }
}
