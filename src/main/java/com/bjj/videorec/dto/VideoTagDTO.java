package com.bjj.videorec.dto;

import com.bjj.videorec.model.VideoTag;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class VideoTagDTO {
    private Long id;
    private String tagName;
    private Float confidence;
    private String source;
    private Float timestampSeconds;
    private LocalDateTime createdDate;

    public static VideoTagDTO fromEntity(VideoTag tag) {
        VideoTagDTO dto = new VideoTagDTO();
        dto.setId(tag.getId());
        dto.setTagName(tag.getTagName());
        dto.setConfidence(tag.getConfidence());
        dto.setSource(tag.getSource().name());
        dto.setTimestampSeconds(tag.getTimestampSeconds());
        dto.setCreatedDate(tag.getCreatedDate());
        return dto;
    }
}
