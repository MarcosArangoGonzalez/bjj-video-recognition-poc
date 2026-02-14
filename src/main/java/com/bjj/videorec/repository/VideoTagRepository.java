package com.bjj.videorec.repository;

import com.bjj.videorec.model.VideoTag;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface VideoTagRepository extends JpaRepository<VideoTag, Long> {

    List<VideoTag> findByVideoId(Long videoId);

    List<VideoTag> findBySource(VideoTag.TagSource source);

    @Query("SELECT DISTINCT vt.tagName FROM VideoTag vt WHERE vt.tagName LIKE %:search%")
    List<String> findDistinctTagNamesBySearch(@Param("search") String search);

    @Query("SELECT vt FROM VideoTag vt WHERE vt.video.id = :videoId AND vt.source = :source")
    List<VideoTag> findByVideoIdAndSource(@Param("videoId") Long videoId, @Param("source") VideoTag.TagSource source);
}
