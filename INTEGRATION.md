# Integration Guide

This guide explains how to integrate the Video Recognition PoC into your main TFG Maven project.

## Overview

The PoC is designed as a modular component that can be easily integrated into your larger BJJ social platform project. The integration involves copying key classes, updating dependencies, and adapting configuration.

## Step 1: Update Maven Dependencies

Add these dependencies to your main project's `pom.xml`:

```xml
<!-- Google Cloud Video Intelligence -->
<dependency>
    <groupId>com.google.cloud</groupId>
    <artifactId>google-cloud-video-intelligence</artifactId>
    <version>2.40.0</version>
</dependency>

<!-- Google Cloud Storage (if using GCS) -->
<dependency>
    <groupId>com.google.cloud</groupId>
    <artifactId>google-cloud-storage</artifactId>
    <version>2.30.0</version>
</dependency>
```

## Step 2: Copy Backend Classes

Copy these packages from the PoC to your main project:

### Entities (adapt to your existing structure)
- `model/Video.java` → Merge with your existing Video entity
- `model/VideoTag.java` → Add as new entity

**Important:** You likely already have a `Video` entity. Merge the PoC's fields:
```java
// Add these fields to your existing Video entity
@Enumerated(EnumType.STRING)
private AnalysisStatus analysisStatus;

@Column(name = "analysis_error")
private String analysisError;

@OneToMany(mappedBy = "video", cascade = CascadeType.ALL)
private List<VideoTag> tags = new ArrayList<>();
```

### Repositories
- `repository/VideoTagRepository.java` → Copy as-is

### Services
- `service/VideoAnalysisService.java` → Copy and adapt
- `service/VideoTagService.java` → Copy as-is

### Controllers
- `controller/VideoTagController.java` → Copy as-is
- Merge tag endpoints into your existing `VideoController`

### DTOs
- `dto/VideoTagDTO.java` → Copy as-is
- `dto/CreateTagRequest.java` → Copy as-is
- Update your existing `VideoDTO` to include tags

### Configuration
- `config/GoogleCloudConfig.java` → Copy as-is

## Step 3: Update Application Configuration

Add to your `application.yml` or `application.properties`:

```yaml
google:
  cloud:
    project-id: ${GOOGLE_CLOUD_PROJECT_ID}
    credentials:
      location: ${GOOGLE_APPLICATION_CREDENTIALS}
    storage:
      bucket-name: ${GCS_BUCKET_NAME}
```

## Step 4: Database Migration

Create a migration script (Flyway/Liquibase) to add the `video_tags` table:

```sql
CREATE TABLE video_tags (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    video_id BIGINT NOT NULL,
    tag_name VARCHAR(255) NOT NULL,
    confidence FLOAT,
    source VARCHAR(20) NOT NULL,
    timestamp_seconds FLOAT,
    created_date TIMESTAMP NOT NULL,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

CREATE INDEX idx_video_tags_video_id ON video_tags(video_id);
CREATE INDEX idx_video_tags_source ON video_tags(source);
CREATE INDEX idx_video_tags_name ON video_tags(tag_name);
```

If using JPA auto-ddl, add the `analysisStatus` and `analysisError` columns to your videos table:

```sql
ALTER TABLE videos 
ADD COLUMN analysis_status VARCHAR(20) DEFAULT 'PENDING',
ADD COLUMN analysis_error TEXT;
```

## Step 5: Integrate Frontend Components

### Option A: Copy React Components
If your main project uses React:

1. Copy `frontend/src/components/TagDisplay.jsx`
2. Copy `frontend/src/components/TagEditor.jsx`
3. Copy `frontend/src/services/api.js` (merge with existing API service)
4. Integrate into your video detail page

### Option B: Adapt to Your Framework
If using a different frontend framework, replicate the functionality:

- **TagDisplay**: Shows auto vs manual tags with visual distinction
- **TagEditor**: Form to add manual tags with timestamp
- **API calls**: Use the endpoints documented in `API.md`

## Step 6: Async Processing (Production)

The PoC processes videos synchronously. For production, make it asynchronous:

### Add Spring Async Support

```java
@Configuration
@EnableAsync
public class AsyncConfig {
    @Bean
    public Executor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(2);
        executor.setMaxPoolSize(5);
        executor.setQueueCapacity(100);
        executor.setThreadNamePrefix("video-analysis-");
        executor.initialize();
        return executor;
    }
}
```

### Update VideoAnalysisService

```java
@Async
public CompletableFuture<Void> analyzeVideoAsync(Long videoId, Path videoPath) {
    analyzeVideo(videoId, videoPath);
    return CompletableFuture.completedFuture(null);
}
```

### Update VideoService

```java
// In uploadVideo method
videoAnalysisService.analyzeVideoAsync(videoId, videoPath)
    .exceptionally(ex -> {
        log.error("Async analysis failed", ex);
        return null;
    });
```

## Step 7: Google Cloud Storage Integration

For production, upload videos to GCS instead of local storage:

```java
@Service
public class GcsStorageService {
    
    @Autowired
    private GoogleCloudConfig config;
    
    public String uploadToGcs(MultipartFile file) throws IOException {
        Storage storage = StorageOptions.getDefaultInstance().getService();
        String blobName = UUID.randomUUID().toString() + "-" + file.getOriginalFilename();
        
        BlobId blobId = BlobId.of(config.getStorage().getBucketName(), blobName);
        BlobInfo blobInfo = BlobInfo.newBuilder(blobId)
                .setContentType(file.getContentType())
                .build();
                
        storage.create(blobInfo, file.getBytes());
        
        return String.format("gs://%s/%s", 
            config.getStorage().getBucketName(), blobName);
    }
}
```

## Step 8: Security Considerations

### Authentication
Ensure only authenticated users can:
- Upload videos
- Add/edit/delete tags
- View videos (based on privacy settings)

### Authorization
Add Spring Security checks:
```java
@PreAuthorize("@videoSecurityService.canModifyVideo(#videoId, authentication)")
public VideoTag addManualTag(Long videoId, String tagName, Float timestamp) {
    // ...
}
```

## Step 9: Testing

Create integration tests for the new functionality:

```java
@SpringBootTest
@AutoConfigureMockMvc
class VideoTagIntegrationTest {
    
    @Test
    void shouldAddManualTag() {
        // Test tag creation
    }
    
    @Test
    void shouldAnalyzeVideo() {
        // Test video analysis (with mocked Google Cloud API)
    }
}
```

## Step 10: Deployment

### Environment Variables
Set these in your production environment:
```bash
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GCS_BUCKET_NAME=your-bucket-name
```

### Docker (if applicable)
Add to your `Dockerfile`:
```dockerfile
COPY credentials.json /app/credentials.json
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json
```

## Checklist

- [ ] Dependencies added to `pom.xml`
- [ ] Entities merged/created
- [ ] Repositories copied
- [ ] Services integrated
- [ ] Controllers integrated
- [ ] Database migration executed
- [ ] Frontend components integrated
- [ ] Async processing configured
- [ ] GCS integration (if needed)
- [ ] Security rules added
- [ ] Tests written
- [ ] Environment variables configured
- [ ] Documentation updated

## Support

If you encounter issues during integration:
1. Check the PoC's `SETUP.md` for configuration details
2. Review `API.md` for endpoint specifications
3. Examine the PoC's working code as reference
4. Test each component independently before full integration
