# BJJ Video Recognition PoC

A proof-of-concept application demonstrating automated video analysis for Brazilian Jiu-Jitsu techniques using Google Cloud Video Intelligence API.

## Features

- 🎥 **Video Upload**: Drag-and-drop interface for uploading BJJ videos
- 🤖 **Auto-Tagging**: Automatic detection of labels, on-screen text, and scene changes
- 🏷️ **Manual Tagging**: Add custom technique tags with timestamps
- 📊 **Tag Management**: View, edit, and delete both auto and manual tags
- 💾 **H2 Database**: In-memory database for quick testing
- 🎨 **Modern UI**: Clean, responsive React interface with Tailwind CSS

## Tech Stack

**Backend:**
- Spring Boot 3.2
- Google Cloud Video Intelligence API
- JPA/Hibernate
- H2 Database
- Maven

**Frontend:**
- React 18
- Vite
- Tailwind CSS
- Axios

## Quick Start

### Prerequisites
- Java 17+
- Node.js 18+
- Maven 3.6+
- Google Cloud account with Video Intelligence API enabled

### Setup

1. **Clone and navigate:**
   ```bash
   cd bjj-video-recognition-poc
   ```

2. **Configure Google Cloud credentials:**
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"
   export GOOGLE_CLOUD_PROJECT_ID="your-project-id"
   ```

3. **Start backend:**
   ```bash
   mvn spring-boot:run
   ```

4. **Start frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

5. **Open browser:**
   Navigate to `http://localhost:3000`

## Documentation

- [📖 Setup Guide](SETUP.md) - Detailed setup instructions
- [📚 API Documentation](API.md) - REST API reference
- [🔗 Integration Guide](INTEGRATION.md) - How to integrate into your main project

## Project Structure

```
bjj-video-recognition-poc/
├── src/main/java/com/bjj/videorec/
│   ├── model/              # JPA entities
│   ├── repository/         # Data access layer
│   ├── service/            # Business logic
│   ├── controller/         # REST endpoints
│   ├── dto/                # Data transfer objects
│   └── config/             # Configuration classes
├── frontend/
│   └── src/
│       ├── components/     # React components
│       └── services/       # API client
└── docs/                   # Documentation
```

## How It Works

1. **Upload**: User uploads a BJJ video through the web interface
2. **Analysis**: Google Cloud Video Intelligence API analyzes the video
3. **Auto-Tags**: System generates tags for:
   - General labels (e.g., "martial arts", "grappling")
   - On-screen text (e.g., tournament names, scores)
   - Scene changes (for video segmentation)
4. **Manual Tags**: User can add custom technique tags (e.g., "Armbar", "Triangle")
5. **Review**: Both auto and manual tags are displayed with confidence scores and timestamps

## Cost Considerations

- **Free Tier**: 1,000 minutes/month
- **After Free Tier**: ~$0.10/minute
- Use short test videos during development

## Future Enhancements

For integration into your main TFG project, consider:
- Async video processing with job queues
- Google Cloud Storage for video hosting
- Custom ML models for BJJ-specific technique recognition
- User authentication and authorization
- Video playback with tag timeline
- Advanced search and filtering

## License

This is a proof-of-concept for educational purposes.

## Author

Created as part of a TFG (Trabajo de Fin de Grado) project for a BJJ social platform.
