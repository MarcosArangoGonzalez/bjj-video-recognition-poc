package com.bjj.videorec.model;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "videos")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class Video {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String filename;

    @Column(name = "gcs_uri")
    private String gcsUri;

    @Column(name = "upload_date", nullable = false)
    private LocalDateTime uploadDate;

    @Column(name = "duration_seconds")
    private Integer durationSeconds;

    @Enumerated(EnumType.STRING)
    @Column(name = "analysis_status", nullable = false)
    private AnalysisStatus analysisStatus;

    @Column(name = "analysis_error")
    private String analysisError;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    private User user;

    @OneToMany(mappedBy = "video", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<VideoTag> tags = new ArrayList<>();

    @PrePersist
    protected void onCreate() {
        uploadDate = LocalDateTime.now();
        if (analysisStatus == null) {
            analysisStatus = AnalysisStatus.PENDING;
        }
    }

    public void addTag(VideoTag tag) {
        tags.add(tag);
        tag.setVideo(this);
    }

    public void removeTag(VideoTag tag) {
        tags.remove(tag);
        tag.setVideo(null);
    }

    public enum AnalysisStatus {
        PENDING,
        PROCESSING,
        COMPLETED,
        FAILED
    }
}
