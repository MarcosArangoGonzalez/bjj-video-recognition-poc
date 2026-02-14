package com.bjj.videorec.dto;

import com.bjj.videorec.model.Video;
import com.bjj.videorec.model.VideoTag;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class VideoDTO {
    private Long id;
    private String filename;
    private LocalDateTime uploadDate;
    private Integer durationSeconds;
    private String analysisStatus;
    private String analysisError;
    private List<VideoTagDTO> tags;

    public static VideoDTO fromEntity(Video video) {
        VideoDTO dto = new VideoDTO();
        dto.setId(video.getId());
        dto.setFilename(video.getFilename());
        dto.setUploadDate(video.getUploadDate());
        dto.setDurationSeconds(video.getDurationSeconds());
        dto.setAnalysisStatus(video.getAnalysisStatus().name());
        dto.setAnalysisError(video.getAnalysisError());
        dto.setTags(video.getTags().stream()
                .map(VideoTagDTO::fromEntity)
                .collect(Collectors.toList()));
        return dto;
    }
}
