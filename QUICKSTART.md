# Quick Start Guide: YOLOv8 + Spring AI + Gemini Integration

This guide will help you get the BJJ video analysis system running with the new two-stage architecture.

## Architecture Overview

```
Video Upload → YOLOv8 (Pose Extraction) → Gemini (Reasoning) → Tags
```

**Stage 1 (YOLOv8)**: Extracts pose keypoints, body positions  
**Stage 2 (Gemini)**: Analyzes video with pose context for technique detection

## Setup Steps

### 1. Python YOLOv8 Service

```bash
# Navigate to project root
cd /home/marcos/Escritorio/bjj-video-recognition-poc

# Run setup script
./setup_yolov8_service.sh

# Edit configuration
nano python/.env
# Add your Roboflow API key: ROBOFLOW_API_KEY=your_key_here

# (Optional) Download Roboflow datasets
cd python
source venv/bin/activate
python3 roboflow_integration.py --download
python3 roboflow_integration.py --merge ../annotations.json

# Start the service
python3 yolov8_service.py
# Service runs on http://localhost:8081
```

### 2. Spring Boot Application

```bash
# Add YOLOv8 configuration (already done via yolov8.properties)
# No changes needed to application.properties

# Build and run
mvn clean install
mvn spring-boot:run
# Application runs on http://localhost:8080
```

### 3. Test the Integration

#### Option A: Using cURL

```bash
# Login
TOKEN=$(curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"password123"}' \
  | jq -r '.token')

# Upload video for analysis
curl -X POST http://localhost:8080/api/videos/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@uploads/sample_bjj_video.mp4" \
  -F "title=Test Video with YOLOv8"

# Check analysis results
VIDEO_ID=1  # Use the ID from upload response
curl http://localhost:8080/api/videos/$VIDEO_ID/tags \
  -H "Authorization: Bearer $TOKEN"
```

#### Option B: Using Docker Compose

```bash
# Build and start services
docker-compose up --build

# The Python service will be available at http://localhost:8081
# Spring Boot will connect to it automatically
```

## Expected Workflow

1. **User uploads video** via `/api/videos/upload`
2. **YOLOv8 service** analyzes video and extracts pose keypoints
3. **Spring AI** receives pose data and video
4. **Gemini** analyzes with enhanced context from poses
5. **VideoTags** created with detected techniques

## Logs to Monitor

### Python Service Logs
```
INFO:werkzeug: * Running on http://0.0.0.0:8081
Processing video: test.mp4 at 1 FPS
Processed 60 frames from 1800 total
```

### Spring Boot Logs
```
YOLOv8 extracted poses from 60 frames
>>>> VIDEO+POSE AI RESPONSE: {...}
Native Gemini analysis completed: 5 techniques detected
```

## Configuration Options

### Adjust Frame Sampling Rate

**Python service** (python/.env):
```
DEFAULT_FPS=1  # Extract 1 frame per second
```

**Spring Boot** (yolov8.properties):
```
yolov8.service.fps=1
```

### Disable YOLOv8 (Fallback to Gemini-only)

```properties
yolov8.service.enabled=false
```

### Adjust Timeout for Long Videos

```properties
yolov8.service.timeout=120000  # 2 minutes
```

## Troubleshooting

### YOLOv8 Service Not Starting

```bash
# Check Python dependencies
cd python
source venv/bin/activate
pip install -r requirements.txt

# Check port availability
lsof -i :8081

# Check logs
python3 yolov8_service.py --debug
```

### Spring Boot Can't Connect to YOLOv8

```bash
# Test YOLOv8 health endpoint
curl http://localhost:8081/health

# Check YOLOv8 configuration in yolov8.properties
# Verify URL matches Python service
```

### No Pose Data in Analysis

Check logs for:
```
YOLOv8 analysis failed, falling back to Gemini-only
```

This means YOLOv8 service is unavailable. Verify it's running:
```bash
curl http://localhost:8081/health
```

### Low Detection Accuracy

1. **Fine-tune YOLOv8** on Roboflow + annotations.json datasets
2. **Adjust FPS**: Higher FPS = more context but slower
3. **Review prompt engineering**: Check `BJJTechniquePrompt.java`

## Performance Benchmarks

**Expected latency** (1-minute video):
- YOLOv8 extraction (CPU): ~5-10 seconds
- Gemini analysis: ~10-20 seconds
- **Total**: ~15-30 seconds

**Optimization**:
- Use GPU for YOLOv8: Update docker-compose.yml
- Reduce FPS to 0.5 (1 frame every 2 seconds)
- Run YOLOv8 and Gemini in parallel (future enhancement)

## Next Steps

1. **Train custom model**: Use Roboflow datasets + annotations.json
2. **Add position classifier**: Predict guard/mount/etc from keypoints
3. **Implement caching**: Store pose data to avoid reprocessing
4. **Add metrics**: Track accuracy vs. annotations.json ground truth

## Support

For issues or questions:
- Check implementation_plan.md for detailed architecture
- Review ARCHITECTURE.md for system design
- Examine logs in both Python and Spring Boot services
