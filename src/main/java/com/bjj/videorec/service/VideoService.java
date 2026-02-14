package com.bjj.videorec.service;

import com.bjj.videorec.model.User;
import com.bjj.videorec.model.Video;
import com.bjj.videorec.repository.VideoRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class VideoService {

    private final VideoRepository videoRepository;
    private final VideoAnalysisService videoAnalysisService;

    @Value("${app.video.upload-dir}")
    private String uploadDir;

    @Value("${app.video.allowed-extensions}")
    private String allowedExtensions;

    /**
     * Upload and save video file
     */
    @Transactional
    public Video uploadVideo(MultipartFile file, User user) throws IOException {
        // Validate file
        validateVideoFile(file);

        // Create upload directory if not exists
        Path uploadPath = Paths.get(uploadDir);
        if (!Files.exists(uploadPath)) {
            Files.createDirectories(uploadPath);
        }

        // Generate unique filename
        String originalFilename = file.getOriginalFilename();
        String extension = getFileExtension(originalFilename);
        String uniqueFilename = UUID.randomUUID().toString() + "." + extension;
        Path filePath = uploadPath.resolve(uniqueFilename);

        // Save file
        Files.copy(file.getInputStream(), filePath, StandardCopyOption.REPLACE_EXISTING);
        log.info("Video uploaded: {}", uniqueFilename);

        // Create video entity
        Video video = new Video();
        video.setFilename(originalFilename);
        video.setGcsUri(filePath.toString()); // For PoC, using local path instead of GCS
        video.setAnalysisStatus(Video.AnalysisStatus.PENDING);
        video.setUser(user);

        video = videoRepository.save(video);

        // Trigger async analysis
        final Long videoId = video.getId();
        final Path videoPath = filePath;

        // In production, this should be done asynchronously with @Async
        // For PoC, we'll do it synchronously
        try {
            videoAnalysisService.analyzeVideo(videoId, videoPath);
        } catch (Exception e) {
            log.error("Failed to analyze video: {}", uniqueFilename, e);
            // Video is saved but analysis failed
        }

        return videoRepository.findById(videoId).orElse(video);
    }

    /**
     * Get all videos
     */
    public List<Video> getAllVideos() {
        return videoRepository.findByOrderByUploadDateDesc();
    }

    /**
     * Get video by ID
     */
    public Video getVideoById(Long id) {
        return videoRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Video not found: " + id));
    }

    /**
     * Delete video
     */
    @Transactional
    public void deleteVideo(Long id) {
        Video video = getVideoById(id);

        // Delete physical file
        try {
            Path filePath = Paths.get(video.getGcsUri());
            Files.deleteIfExists(filePath);
        } catch (IOException e) {
            log.error("Failed to delete video file: {}", video.getFilename(), e);
        }

        videoRepository.delete(video);
        log.info("Video deleted: {}", video.getFilename());
    }

    /**
     * Validate video file
     */
    private void validateVideoFile(MultipartFile file) {
        if (file.isEmpty()) {
            throw new IllegalArgumentException("File is empty");
        }

        String filename = file.getOriginalFilename();
        if (filename == null || filename.isEmpty()) {
            throw new IllegalArgumentException("Invalid filename");
        }

        String extension = getFileExtension(filename).toLowerCase();
        List<String> allowed = List.of(allowedExtensions.split(","));

        if (!allowed.contains(extension)) {
            throw new IllegalArgumentException(
                    "Invalid file extension. Allowed: " + allowedExtensions);
        }
    }

    /**
     * Get file extension
     */
    private String getFileExtension(String filename) {
        int lastDotIndex = filename.lastIndexOf('.');
        if (lastDotIndex == -1) {
            return "";
        }
        return filename.substring(lastDotIndex + 1);
    }
}
