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
- [🧭 Detailed Pipeline Guide](PIPELINE_DE_ANALISIS_DE_VIDEO_DETALLADO.md) - End-to-end flow upload → analysis → output (classes, model files, and libraries)
- [🎯 Accuracy Configuration](ACCURACY_CONFIGURATION.md) - Accuracy assumptions and detection configuration
- [🧩 Hybrid Detection Summary](HYBRID_DETECTION_SUMMARY.md) - Hybrid detector architecture and model distribution

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
2. **Pose Extraction (YOLOv8)**: A Python microservice extracts pose keypoints frame by frame.
3. **Hybrid Detection**:
   - **Local Random Forest** predicts BJJ positions (18 classes, ~95.6% classification accuracy as documented in `ACCURACY_CONFIGURATION.md` and `HYBRID_DETECTION_SUMMARY.md`).
   - **Roboflow model** complements with submissions/sweeps/transitions/takedowns.
4. **Gemini Validation (Spring AI)**:
   - Gemini receives the video plus pose/hybrid context.
   - Uses **hybrid reasoning**: geometric constraints for positions + biomechanical reasoning for submissions.
   - If Gemini returns no detections, the system falls back to hybrid detector output.
5. **Tag Generation**: Detected techniques are stored as auto-tags with confidence and timestamps.
6. **Review/Edit**: User can review, edit, and add manual tags.

### Pipeline Explanation (Spanish)

El pipeline real de análisis está orquestado en `BJJPoseDetectionService`:

1. **Análisis base de vídeo**: `VideoAnalysisService` gestiona estado/transacciones y delega el análisis técnico.
2. **YOLOv8 + detector híbrido**: se generan keypoints y predicciones por frame.
3. **Gemini como árbitro final**: valida/refina las detecciones usando contexto visual + geométrico.
4. **Fallback robusto**: si Gemini falla o devuelve vacío, se usan resultados del detector híbrido.

### Relative Weight in Analysis (Spanish)

No se usan pesos aditivos tipo “40/30/30”, sino una **jerarquía de decisión**:

- **Random Forest (alto peso en posiciones)**:
  - Es la base local para posiciones.
  - Precisión reportada en el repo: ~95.6% para clases de posición.
- **Geometría (alto peso en la lógica de posición)**:
  - Reglas por ángulos/vectores y relaciones espaciales en prompts/heurísticas.
  - Ayuda a distinguir posiciones y evitar confusiones visuales.
- **Gemini (peso final en decisión)**:
  - Actúa como capa de validación semántica/biomecánica sobre el vídeo completo.
  - Cuando Gemini devuelve detecciones válidas, esas son las que se publican.
  - Si no devuelve resultados, el sistema hace fallback al detector híbrido.

### Project Overview (Spanish)

Este repositorio es una PoC para etiquetar técnicas de Brazilian Jiu-Jitsu en vídeo combinando:

- **Backend Java/Spring Boot** (API, persistencia, orquestación),
- **Frontend React** (subida y gestión de tags),
- **Servicios Python de visión** (YOLOv8 + clasificadores híbridos),
- **LLM multimodal (Gemini)** para validación contextual.

Objetivo: producir tags automáticos útiles para revisión técnica, manteniendo un flujo robusto con fallback cuando algún componente falla.

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
