package com.bjj.videorec.controller;

import com.bjj.videorec.dto.VideoDTO;
import com.bjj.videorec.model.User;
import com.bjj.videorec.model.Video;
import com.bjj.videorec.repository.UserRepository;
import com.bjj.videorec.service.VideoService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/videos")
@RequiredArgsConstructor
@Slf4j
@CrossOrigin(origins = "*")
public class VideoController {

    private final VideoService videoService;
    private final UserRepository userRepository;

    /**
     * Upload a new video
     */
    @PostMapping("/upload")
    public ResponseEntity<VideoDTO> uploadVideo(@RequestParam("file") MultipartFile file,
            Authentication authentication) {
        try {
            String username = (authentication != null) ? authentication.getName() : "poc_user";
            User user = userRepository.findByUsername(username)
                    .orElseThrow(() -> new RuntimeException("User not found: " + username));

            log.info("Uploading video: {} for user: {}", file.getOriginalFilename(), username);
            Video video = videoService.uploadVideo(file, user);
            return ResponseEntity.ok(VideoDTO.fromEntity(video));
        } catch (IllegalArgumentException e) {
            log.error("Invalid video upload request", e);
            return ResponseEntity.badRequest().build();
        } catch (Exception e) {
            log.error("Failed to upload video", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }

    /**
     * Get all videos
     */
    @GetMapping
    public ResponseEntity<List<VideoDTO>> getAllVideos() {
        List<Video> videos = videoService.getAllVideos();
        List<VideoDTO> dtos = videos.stream()
                .map(VideoDTO::fromEntity)
                .collect(Collectors.toList());
        return ResponseEntity.ok(dtos);
    }

    /**
     * Get video by ID
     */
    @GetMapping("/{id}")
    public ResponseEntity<VideoDTO> getVideoById(@PathVariable Long id) {
        try {
            Video video = videoService.getVideoById(id);
            return ResponseEntity.ok(VideoDTO.fromEntity(video));
        } catch (RuntimeException e) {
            return ResponseEntity.notFound().build();
        }
    }

    /**
     * Delete video
     */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteVideo(@PathVariable Long id) {
        try {
            videoService.deleteVideo(id);
            return ResponseEntity.noContent().build();
        } catch (RuntimeException e) {
            return ResponseEntity.notFound().build();
        }
    }
}
