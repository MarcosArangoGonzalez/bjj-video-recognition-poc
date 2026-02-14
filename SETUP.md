# BJJ Video Recognition PoC - Setup Guide

## Prerequisites

- Java 17 or higher
- Maven 3.6+
- Node.js 18+ and npm
- Google Cloud account

## Google Cloud Setup

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter project name (e.g., `bjj-video-recognition`)
4. Click "Create"

### 2. Enable Video Intelligence API

1. In the Cloud Console, go to "APIs & Services" → "Library"
2. Search for "Video Intelligence API"
3. Click on it and press "Enable"

### 3. Create Service Account Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "Service Account"
3. Enter a name (e.g., `video-analysis-service`)
4. Click "Create and Continue"
5. Grant role: "Video Intelligence Admin"
6. Click "Done"
7. Click on the created service account
8. Go to "Keys" tab → "Add Key" → "Create new key"
9. Choose "JSON" format
10. Download the JSON file

### 4. Configure Credentials

**Option A: Environment Variable (Recommended)**
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/credentials.json"
export GOOGLE_CLOUD_PROJECT_ID="your-project-id"
export GCS_BUCKET_NAME="bjj-videos-poc"
```

**Option B: Application Properties**
1. Place the JSON file in `src/main/resources/` (rename to `gcp-credentials.json`)
2. Update `application.yml`:
```yaml
google:
  cloud:
    project-id: your-project-id
    credentials:
      location: classpath:gcp-credentials.json
```

### 5. Create Storage Bucket (Optional)

For production use with Google Cloud Storage:
```bash
gsutil mb -p your-project-id gs://bjj-videos-poc
```

## Backend Setup

### 1. Navigate to Project Directory
```bash
cd bjj-video-recognition-poc
```

### 2. Build the Project
```bash
mvn clean install
```

### 3. Run the Application
```bash
mvn spring-boot:run
```

The backend will start on `http://localhost:8080`

### 4. Access H2 Console (Optional)
- URL: `http://localhost:8080/h2-console`
- JDBC URL: `jdbc:h2:mem:videodb`
- Username: `sa`
- Password: (leave empty)

## Frontend Setup

### 1. Navigate to Frontend Directory
```bash
cd frontend
```

### 2. Install Dependencies
```bash
npm install
```

### 3. Run Development Server
```bash
npm run dev
```

The frontend will start on `http://localhost:3000`

## Testing the Application

### 1. Upload a Video
1. Open `http://localhost:3000` in your browser
2. Click or drag-and-drop a BJJ video (MP4, AVI, MOV, or MKV)
3. Click "Upload and Analyze"
4. Wait for analysis to complete

### 2. View Auto-Generated Tags
- Auto-generated tags will appear under "Auto-Generated Tags"
- Tags include confidence scores and timestamps

### 3. Add Manual Tags
1. Select a video from the list
2. Use the "Add Manual Tag" form
3. Enter technique names (e.g., "Armbar", "Triangle")
4. Optionally add timestamp
5. Click "Add Tag"

## Troubleshooting

### "Failed to upload video"
- Check file size (max 500MB)
- Verify file format (MP4, AVI, MOV, MKV)
- Check backend logs for errors

### "Video analysis failed"
- Verify Google Cloud credentials are configured
- Check that Video Intelligence API is enabled
- Ensure you have sufficient API quota
- Review backend logs: `tail -f logs/spring-boot-logger.log`

### "Connection refused" errors
- Ensure backend is running on port 8080
- Ensure frontend is running on port 3000
- Check firewall settings

## Cost Considerations

### Google Cloud Video Intelligence Pricing
- **Free Tier**: First 1,000 minutes/month
- **After Free Tier**: ~$0.10 per minute

### Tips to Minimize Costs
- Use short test videos during development
- Delete analyzed videos when done testing
- Monitor usage in Google Cloud Console

## Next Steps

Once you have the PoC working:
1. Test with various BJJ videos
2. Evaluate auto-tagging accuracy
3. Document which techniques are recognized well
4. Plan integration into your main TFG project
