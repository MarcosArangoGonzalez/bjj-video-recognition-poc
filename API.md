# API Documentation

Base URL: `http://localhost:8080/api`

## Video Endpoints

### Upload Video
Upload a video file for analysis.

**Endpoint:** `POST /videos/upload`

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` (video file)

**Response:**
```json
{
  "id": 1,
  "filename": "bjj-match.mp4",
  "uploadDate": "2024-12-05T12:00:00",
  "durationSeconds": null,
  "analysisStatus": "PROCESSING",
  "analysisError": null,
  "tags": []
}
```

**Status Codes:**
- `200 OK`: Video uploaded successfully
- `400 Bad Request`: Invalid file or format
- `500 Internal Server Error`: Upload failed

---

### Get All Videos
Retrieve all uploaded videos.

**Endpoint:** `GET /videos`

**Response:**
```json
[
  {
    "id": 1,
    "filename": "bjj-match.mp4",
    "uploadDate": "2024-12-05T12:00:00",
    "durationSeconds": 180,
    "analysisStatus": "COMPLETED",
    "analysisError": null,
    "tags": [...]
  }
]
```

---

### Get Video by ID
Retrieve a specific video with all its tags.

**Endpoint:** `GET /videos/{id}`

**Response:**
```json
{
  "id": 1,
  "filename": "bjj-match.mp4",
  "uploadDate": "2024-12-05T12:00:00",
  "durationSeconds": 180,
  "analysisStatus": "COMPLETED",
  "analysisError": null,
  "tags": [
    {
      "id": 1,
      "tagName": "martial arts",
      "confidence": 0.95,
      "source": "AUTO",
      "timestampSeconds": 10.5,
      "createdDate": "2024-12-05T12:01:00"
    }
  ]
}
```

**Status Codes:**
- `200 OK`: Video found
- `404 Not Found`: Video doesn't exist

---

### Delete Video
Delete a video and all its tags.

**Endpoint:** `DELETE /videos/{id}`

**Status Codes:**
- `204 No Content`: Video deleted successfully
- `404 Not Found`: Video doesn't exist

---

## Tag Endpoints

### Get Video Tags
Get all tags for a specific video.

**Endpoint:** `GET /videos/{videoId}/tags`

**Response:**
```json
[
  {
    "id": 1,
    "tagName": "Armbar",
    "confidence": null,
    "source": "MANUAL",
    "timestampSeconds": 45.0,
    "createdDate": "2024-12-05T12:05:00"
  },
  {
    "id": 2,
    "tagName": "grappling",
    "confidence": 0.92,
    "source": "AUTO",
    "timestampSeconds": 0.0,
    "createdDate": "2024-12-05T12:01:00"
  }
]
```

---

### Add Manual Tag
Add a manual tag to a video.

**Endpoint:** `POST /videos/{videoId}/tags`

**Request:**
```json
{
  "tagName": "Triangle Choke",
  "timestampSeconds": 120.5
}
```

**Response:**
```json
{
  "id": 3,
  "tagName": "Triangle Choke",
  "confidence": null,
  "source": "MANUAL",
  "timestampSeconds": 120.5,
  "createdDate": "2024-12-05T12:10:00"
}
```

**Status Codes:**
- `201 Created`: Tag added successfully
- `400 Bad Request`: Invalid request (missing tagName)
- `404 Not Found`: Video doesn't exist

---

### Update Tag
Update an existing tag.

**Endpoint:** `PUT /videos/{videoId}/tags/{tagId}`

**Request:**
```json
{
  "tagName": "Modified Triangle",
  "timestampSeconds": 125.0
}
```

**Response:**
```json
{
  "id": 3,
  "tagName": "Modified Triangle",
  "confidence": null,
  "source": "MANUAL",
  "timestampSeconds": 125.0,
  "createdDate": "2024-12-05T12:10:00"
}
```

**Status Codes:**
- `200 OK`: Tag updated successfully
- `404 Not Found`: Tag or video doesn't exist

---

### Delete Tag
Delete a tag from a video.

**Endpoint:** `DELETE /videos/{videoId}/tags/{tagId}`

**Status Codes:**
- `204 No Content`: Tag deleted successfully
- `404 Not Found`: Tag or video doesn't exist

---

### Search Tags
Search for tag names across all videos.

**Endpoint:** `GET /videos/{videoId}/tags/search?q={query}`

**Parameters:**
- `q`: Search query (string)

**Response:**
```json
[
  "Armbar",
  "Arm Triangle",
  "Armlock"
]
```

---

## Data Models

### Video
```typescript
{
  id: number
  filename: string
  uploadDate: string (ISO 8601)
  durationSeconds: number | null
  analysisStatus: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED"
  analysisError: string | null
  tags: VideoTag[]
}
```

### VideoTag
```typescript
{
  id: number
  tagName: string
  confidence: number | null  // 0.0 to 1.0 for AUTO tags, null for MANUAL
  source: "AUTO" | "MANUAL"
  timestampSeconds: number | null
  createdDate: string (ISO 8601)
}
```

---

## Error Responses

All error responses follow this format:

```json
{
  "timestamp": "2024-12-05T12:00:00",
  "status": 400,
  "error": "Bad Request",
  "message": "Invalid file extension. Allowed: mp4,avi,mov,mkv",
  "path": "/api/videos/upload"
}
```
