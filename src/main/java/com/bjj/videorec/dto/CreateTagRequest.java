package com.bjj.videorec.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class CreateTagRequest {
    @NotBlank(message = "Tag name is required")
    private String tagName;

    private Float timestampSeconds;
}
