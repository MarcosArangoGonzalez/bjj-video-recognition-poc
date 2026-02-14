package com.bjj.videorec.repository;

import com.bjj.videorec.model.Video;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface VideoRepository extends JpaRepository<Video, Long> {

    List<Video> findByAnalysisStatus(Video.AnalysisStatus status);

    List<Video> findByOrderByUploadDateDesc();
}
