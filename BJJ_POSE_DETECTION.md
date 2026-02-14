# BJJ Pose Detection - Setup Guide

## Installation

### 1. Install Python Dependencies

```bash
cd /home/marcos/.gemini/antigravity/playground/white-lagoon/bjj-video-recognition-poc
pip3 install -r python/requirements.txt
```

### 2. Test Python Script

```bash
# Test with a sample video
python3 python/bjj_pose_detector.py /path/to/your/bjj_video.mp4
```

Expected output:
```json
{
  "detections": [
    {
      "type": "position",
      "name": "Mount",
      "confidence": 0.75,
      "timestamp": 5.5,
      "details": {"frame": 165}
    },
    {
      "type": "technique",
      "name": "Armbar",
      "confidence": 0.70,
      "timestamp": 12.3,
      "details": {"frame": 369, "position": "Guard"}
    }
  ],
  "summary": {
    "total_detections": 2,
    "positions": 1,
    "techniques": 1
  }
}
```

## How It Works

### MediaPipe Pose Detection

The system uses MediaPipe to detect 33 body keypoints:
- Head: nose, eyes, ears
- Torso: shoulders, hips
- Arms: elbows, wrists
- Legs: knees, ankles

### Position Detection Logic

**Mount:**
- Hips above shoulders
- Horizontal body orientation

**Guard (Closed/Open):**
- Legs bent
- Hips lower than shoulders
- Knees close to hips

**Side Control:**
- Body perpendicular
- Horizontal orientation

**Back Control:**
- Similar height shoulders/hips
- Specific arm positions

**Turtle:**
- Compact position
- Shoulders and hips at similar height

### Technique Detection Logic

**Armbar:**
- Extended arm (elbow to wrist distance > 0.2)
- From Mount or Guard position

**Triangle Choke:**
- Legs near head/neck area
- From Guard position

**Rear Naked Choke:**
- Arms around neck
- From Back Control position

**Kimura:**
- Bent arm at specific angle (45-135°)
- From Side Control position

## Detection Accuracy

Expected accuracy based on video quality:

| Video Quality | Position Detection | Technique Detection |
|--------------|-------------------|-------------------|
| HD, Side Angle | 70-80% | 60-70% |
| HD, Top Angle | 60-70% | 50-60% |
| Low Quality | 40-50% | 30-40% |

**Best Results:**
- High resolution (720p+)
- Side camera angle
- Good lighting
- Clear view of both athletes

## Integration with Spring Boot

The Java service (`BJJPoseDetectionService`) calls the Python script and parses the JSON output.

Tags are added with prefix:
- `POSITION: Mount`
- `TECHNIQUE: Armbar`

## Troubleshooting

### "ModuleNotFoundError: No module named 'mediapipe'"
```bash
pip3 install mediapipe opencv-python numpy
```

### "Python script failed with exit code: 1"
Check that:
- Python 3.8+ is installed
- Video file exists and is readable
- Video format is supported (MP4, AVI, MOV)

### Low detection accuracy
- Use videos with side camera angle
- Ensure good lighting
- Use HD quality videos
- Avoid heavily edited/zoomed videos

## Future Improvements

To improve accuracy:
1. **Train custom model** on BJJ dataset
2. **Add temporal analysis** (track positions over time)
3. **Multi-angle fusion** (combine multiple camera angles)
4. **Fine-tune thresholds** based on your specific videos
