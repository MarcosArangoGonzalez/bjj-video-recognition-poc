package com.bjj.videorec.service;

import com.bjj.videorec.model.Video;
import com.bjj.videorec.model.VideoTag;
import com.bjj.videorec.repository.VideoRepository;
import com.bjj.videorec.repository.VideoTagRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
@Slf4j
public class VideoTagService {

    private final VideoRepository videoRepository;
    private final VideoTagRepository videoTagRepository;

    /**
     * Add a manual tag to a video
     */
    @Transactional
    public VideoTag addManualTag(Long videoId, String tagName, Float timestampSeconds) {
        Video video = videoRepository.findById(videoId)
                .orElseThrow(() -> new RuntimeException("Video not found: " + videoId));

        VideoTag tag = new VideoTag();
        tag.setTagName(tagName);
        tag.setSource(VideoTag.TagSource.MANUAL);
        tag.setTimestampSeconds(timestampSeconds);
        tag.setConfidence(null); // Manual tags don't have confidence scores

        video.addTag(tag);
        videoRepository.save(video);

        log.info("Added manual tag '{}' to video {}", tagName, videoId);
        return tag;
    }

    /**
     * Update a tag
     */
    @Transactional
    public VideoTag updateTag(Long tagId, String newTagName, Float newTimestamp) {
        VideoTag tag = videoTagRepository.findById(tagId)
                .orElseThrow(() -> new RuntimeException("Tag not found: " + tagId));

        if (newTagName != null && !newTagName.isEmpty()) {
            tag.setTagName(newTagName);
        }
        if (newTimestamp != null) {
            tag.setTimestampSeconds(newTimestamp);
        }

        tag = videoTagRepository.save(tag);
        log.info("Updated tag {}: {}", tagId, newTagName);
        return tag;
    }

    /**
     * Delete a tag
     */
    @Transactional
    public void deleteTag(Long videoId, Long tagId) {
        Video video = videoRepository.findById(videoId)
                .orElseThrow(() -> new RuntimeException("Video not found: " + videoId));

        VideoTag tag = videoTagRepository.findById(tagId)
                .orElseThrow(() -> new RuntimeException("Tag not found: " + tagId));

        video.removeTag(tag);
        videoRepository.save(video);

        log.info("Deleted tag {} from video {}", tagId, videoId);
    }

    /**
     * Get all tags for a video
     */
    public List<VideoTag> getVideoTags(Long videoId) {
        return videoTagRepository.findByVideoId(videoId);
    }

    /**
     * Search tags by name
     */
    public List<String> searchTags(String search) {
        return videoTagRepository.findDistinctTagNamesBySearch(search);
    }
}
