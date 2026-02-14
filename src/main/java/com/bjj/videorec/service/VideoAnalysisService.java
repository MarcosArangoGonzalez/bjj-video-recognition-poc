package com.bjj.videorec.service;

import com.bjj.videorec.model.Video;
import com.bjj.videorec.model.VideoTag;
import com.bjj.videorec.repository.VideoRepository;
import com.bjj.videorec.repository.VideoTagRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.file.Path;
import java.util.List;

@Service
@RequiredArgsConstructor
@Slf4j
public class VideoAnalysisService {

    private final VideoRepository videoRepository;
    private final VideoTagRepository videoTagRepository;
    private final BJJPoseDetectionService bjjPoseDetectionService;

    /**
     * Analyzes a video using Gemini Vision API for BJJ technique detection
     */
    @Transactional
    public void analyzeVideo(Long videoId, Path videoPath) {
        Video video = videoRepository.findById(videoId)
                .orElseThrow(() -> new RuntimeException("Video not found: " + videoId));

        try {
            video.setAnalysisStatus(Video.AnalysisStatus.PROCESSING);
            videoRepository.save(video);

            log.info("Starting Gemini-based analysis for video: {}", video.getFilename());

            // Run Gemini BJJ technique detection
            List<VideoTag> bjjTags = bjjPoseDetectionService.analyzeBJJPoses(video, videoPath);
            bjjTags.forEach(video::addTag);

            video.setAnalysisStatus(Video.AnalysisStatus.COMPLETED);
            videoRepository.save(video);

            log.info("Analysis completed for video: {} - {} techniques detected",
                    video.getFilename(), bjjTags.size());

        } catch (Exception e) {
            log.error("Error analyzing video: {}", video.getFilename(), e);
            video.setAnalysisStatus(Video.AnalysisStatus.FAILED);
            video.setAnalysisError(e.getMessage());
            videoRepository.save(video);
            throw new RuntimeException("Video analysis failed", e);
        }
    }

    /**
     * Get all tags for a video
     */
    public List<VideoTag> getVideoTags(Long videoId) {
        return videoTagRepository.findByVideoId(videoId);
    }

    /**
     * Get only auto-generated tags
     */
    public List<VideoTag> getAutoTags(Long videoId) {
        return videoTagRepository.findByVideoIdAndSource(videoId, VideoTag.TagSource.AUTO);
    }

    /**
     * Get only manual tags
     */
    public List<VideoTag> getManualTags(Long videoId) {
        return videoTagRepository.findByVideoIdAndSource(videoId, VideoTag.TagSource.MANUAL);
    }
}
