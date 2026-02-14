package com.bjj.videorec.controller;

import com.bjj.videorec.dto.CreateTagRequest;
import com.bjj.videorec.dto.VideoTagDTO;
import com.bjj.videorec.model.VideoTag;
import com.bjj.videorec.service.VideoTagService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/videos/{videoId}/tags")
@RequiredArgsConstructor
@Slf4j
@CrossOrigin(origins = "*")
public class VideoTagController {

    private final VideoTagService videoTagService;

    /**
     * Get all tags for a video
     */
    @GetMapping
    public ResponseEntity<List<VideoTagDTO>> getVideoTags(@PathVariable Long videoId) {
        List<VideoTag> tags = videoTagService.getVideoTags(videoId);
        List<VideoTagDTO> dtos = tags.stream()
                .map(VideoTagDTO::fromEntity)
                .collect(Collectors.toList());
        return ResponseEntity.ok(dtos);
    }

    /**
     * Add a manual tag to a video
     */
    @PostMapping
    public ResponseEntity<VideoTagDTO> addTag(
            @PathVariable Long videoId,
            @Valid @RequestBody CreateTagRequest request) {
        try {
            VideoTag tag = videoTagService.addManualTag(
                    videoId,
                    request.getTagName(),
                    request.getTimestampSeconds());
            return ResponseEntity.status(HttpStatus.CREATED)
                    .body(VideoTagDTO.fromEntity(tag));
        } catch (RuntimeException e) {
            log.error("Failed to add tag", e);
            return ResponseEntity.badRequest().build();
        }
    }

    /**
     * Update a tag
     */
    @PutMapping("/{tagId}")
    public ResponseEntity<VideoTagDTO> updateTag(
            @PathVariable Long videoId,
            @PathVariable Long tagId,
            @Valid @RequestBody CreateTagRequest request) {
        try {
            VideoTag tag = videoTagService.updateTag(
                    tagId,
                    request.getTagName(),
                    request.getTimestampSeconds());
            return ResponseEntity.ok(VideoTagDTO.fromEntity(tag));
        } catch (RuntimeException e) {
            log.error("Failed to update tag", e);
            return ResponseEntity.notFound().build();
        }
    }

    /**
     * Delete a tag
     */
    @DeleteMapping("/{tagId}")
    public ResponseEntity<Void> deleteTag(
            @PathVariable Long videoId,
            @PathVariable Long tagId) {
        try {
            videoTagService.deleteTag(videoId, tagId);
            return ResponseEntity.noContent().build();
        } catch (RuntimeException e) {
            log.error("Failed to delete tag", e);
            return ResponseEntity.notFound().build();
        }
    }

    /**
     * Search tags
     */
    @GetMapping("/search")
    public ResponseEntity<List<String>> searchTags(@RequestParam String q) {
        List<String> tags = videoTagService.searchTags(q);
        return ResponseEntity.ok(tags);
    }
}
