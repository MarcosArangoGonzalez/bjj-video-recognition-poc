# Pipeline de análisis de vídeo (detalle técnico)

Este documento explica el flujo completo **desde la subida del vídeo hasta la salida final** del sistema, incluyendo clases Java, microservicios Python, modelos (`.pt`, `.pkl`) y librerías usadas.

---

## 1) Flujo end-to-end (de entrada a salida)

1. **Upload del vídeo (HTTP multipart)**
   - Endpoint: `POST /api/videos/upload`
   - Clase: `src/main/java/com/bjj/videorec/controller/VideoController.java` (`uploadVideo`)
   - El controlador delega en `VideoService.uploadVideo(...)`.

2. **Validación + guardado en disco**
   - Clase: `src/main/java/com/bjj/videorec/service/VideoService.java`
   - Pasos:
     - valida extensión (`app.video.allowed-extensions`)
     - genera nombre único con `UUID`
     - guarda el archivo en `app.video.upload-dir`
     - crea entidad `Video` (`analysisStatus=PENDING`)
     - llama a `videoAnalysisService.analyzeVideo(videoId, videoPath)`

3. **Orquestación de análisis y estado**
   - Clase: `src/main/java/com/bjj/videorec/service/VideoAnalysisService.java`
   - Pasos:
     - marca `PROCESSING`
     - llama a `BJJPoseDetectionService.analyzeBJJPoses(video, videoPath)`
     - añade `VideoTag` generados al vídeo
     - marca `COMPLETED` (o `FAILED` si hay error)

4. **Pipeline técnico de detección (2 etapas)**
   - Clase clave: `src/main/java/com/bjj/videorec/service/BJJPoseDetectionService.java`
   - Lógica:
     - si `yolov8.service.enabled=true` y `YoloV8Service.isHealthy()`:
       - **Stage 1**: YOLOv8 + detector híbrido en Python (`YoloV8Service.analyzeVideo`)
       - **Stage 2**: IA multimodal (Gemini/OpenAI) con contexto de poses (`analyzeVideoWithPoses`)
       - si Gemini devuelve vacío/falla: fallback a extracción desde `poseData` (`extractTechniquesFromPoseData`)
     - si YOLOv8 no está disponible: análisis directo con IA (`analyzeVideo`)
   - Convierte `TechniqueDetection` a `VideoTag`:
     - aplica umbrales (`POSITION: 0.15`, resto `0.50`)
     - normaliza tiempo (`MM:SS` o `timestampSeconds`)
     - guarda texto final del tag con razonamiento/visual cues.

5. **Persistencia y salida para frontend**
   - Entidad/DTO:
     - `Video`, `VideoTag`
     - `VideoDTO`, `VideoTagDTO`
   - Endpoints de lectura:
     - `GET /api/videos`
     - `GET /api/videos/{id}`
     - `GET /api/videos/{videoId}/tags`

---

## 2) Comunicación Java ↔ Python ↔ IA externa

### 2.1 Java → Python (YOLOv8 service)

- Clase cliente HTTP: `src/main/java/com/bjj/videorec/service/YoloV8Service.java`
- Endpoint Python llamado desde Java:
  - `POST /api/analyze-video` (multipart: `video`, `fps`)
  - `GET /health`
- Respuesta mapeada a DTO Java:
  - `src/main/java/com/bjj/videorec/dto/PoseAnalysisResult.java`
  - `src/main/java/com/bjj/videorec/dto/PoseData.java`

### 2.2 Python (extracción de poses + detección híbrida)

- Servicio Flask:
  - `python/yolov8_service.py`
  - endpoints:
    - `GET /health`
    - `POST /api/analyze-video`
    - `POST /api/analyze-frame`
- Flujo interno en `/api/analyze-video`:
  1. abre vídeo con OpenCV
  2. muestrea frames según `fps`
  3. ejecuta YOLOv8 pose por frame
  4. extrae 17 keypoints COCO (`nose`, `left_shoulder`, ...)
  5. ejecuta `HybridBJJDetector.hybrid_predict(...)`
  6. aplica estabilización por majority vote de posición
  7. devuelve JSON con `frames[]` + técnicas detectadas.

### 2.3 Java → Gemini/OpenAI (Spring AI)

- Clase: `src/main/java/com/bjj/videorec/service/SpringAiAnalysisService.java`
- Métodos:
  - `analyzeVideo(File)` (sin contexto de pose)
  - `analyzeVideoWithPoses(File, PoseAnalysisResult)` (con contexto de pose)
- Construcción de prompt:
  - `src/main/java/com/bjj/videorec/util/BJJTechniquePrompt.java`
- Parseo y saneado JSON:
  - `sanitizeJson(...)`, `parseResponse(...)`, fallback heurístico.

---

## 3) Modelos y artefactos (`.pt`, `.pkl`, `.json`)

### 3.1 Archivos presentes en este repo

- `yolov8n.pt` (raíz del proyecto)
  - ruta relativa: `./yolov8n.pt`

### 3.2 Archivos esperados en runtime (no siempre versionados)

- `models/bjj_custom.pt`
  - modelo YOLO custom (si existe, se prioriza sobre base)
  - carga en `python/yolov8_service.py` (`MODEL_PATH`)
- `yolov8n-pose.pt`
  - fallback de Ultralytics si no existe custom
  - carga en `python/yolov8_service.py` (`YOLO('yolov8n-pose.pt')`)
- `models/bjj_pose_classifier.pkl`
  - clasificador local (scikit-learn) para posiciones
  - carga en `python/hybrid_bjj_detector.py`
- `models/label_mapping.json`
  - mapeo índice ↔ nombre de posición del clasificador local
  - carga en `python/hybrid_bjj_detector.py`

### 3.3 Entrenamiento/evaluación de modelos locales

- Script entrenamiento: `python/train_bjj_classifier.py`
  - genera `.pkl` y `label_mapping.json`
- Script evaluación: `python/evaluate_bjj_model_accuracy.py`

---

## 4) Clases/ficheros clave por etapa

- **API subida/listado vídeos**
  - `controller/VideoController.java`
  - `service/VideoService.java`
- **Orquestación análisis**
  - `service/VideoAnalysisService.java`
  - `service/BJJPoseDetectionService.java`
- **Cliente YOLOv8 remoto**
  - `service/YoloV8Service.java`
  - `config/YoloV8Config.java`
- **IA multimodal**
  - `service/SpringAiAnalysisService.java`
  - `util/BJJTechniquePrompt.java`
- **Servicio Python**
  - `python/yolov8_service.py`
  - `python/hybrid_bjj_detector.py`

---

## 5) Librerías concretas usadas

### 5.1 Java (backend)

- **Spring Boot 3.2**
  - `spring-boot-starter-web` (REST, multipart)
  - `spring-boot-starter-data-jpa` (persistencia)
  - `spring-boot-starter-security` (auth)
  - `spring-boot-starter-validation`
- **Spring AI**
  - `spring-ai-vertex-ai-gemini-spring-boot-starter`
  - `spring-ai-openai-spring-boot-starter`
- **JWT**
  - `io.jsonwebtoken:jjwt-*`
- **H2**
  - `com.h2database:h2`
- **Lombok**

Fuente: `pom.xml`

### 5.2 Python (pose/híbrido)

De `python/requirements.txt`:
- `ultralytics` (YOLOv8)
- `torch` (backend DL)
- `opencv-python` (lectura vídeo y frames)
- `flask`, `flask-cors` (microservicio HTTP)
- `scikit-learn` (clasificador local Random Forest)
- `roboflow` (detección complementaria vía API)
- `numpy`, `pillow`, `pandas`
- `python-dotenv`
- `gunicorn`

---

## 6) Salida final que devuelve el sistema

La salida persistida son `VideoTag` (auto-generados), con:
- `tagName` (ej. `POSITION: Mount (...)`)
- `confidence`
- `timestampSeconds`
- `source = AUTO`

Se exponen por API en endpoints de vídeos/tags y se consumen en frontend para revisión/edición.

---

## 7) Resumen técnico corto

- **Entrada**: vídeo subido por usuario (`MultipartFile`)
- **Procesamiento**:
  1. almacenamiento y estado en Java
  2. keypoints + predicciones híbridas en Python (YOLOv8 + clasificador local + Roboflow)
  3. validación semántica en Gemini/OpenAI (Spring AI)
  4. fallback robusto a resultados híbridos si IA no devuelve detecciones
- **Salida**: tags estructurados con técnica, confianza y timestamp, guardados en BD y servidos por API.
