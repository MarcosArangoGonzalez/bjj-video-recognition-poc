# Índice de Clases del Proyecto

## 📦 Paquetes y Clases (33 archivos)

### 🔧 `com.bjj.videorec.config` (6 clases)

| Clase | Propósito | Líneas |
|-------|-----------|--------|
| [`SpringAiConfig`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/config/SpringAiConfig.java) | Bean ChatClient.Builder para Spring AI | ~30 |
| [`SecurityConfig`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/config/SecurityConfig.java) | Configuración Spring Security + JWT | ~70 |
| [`JwtTokenProvider`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/config/JwtTokenProvider.java) | Generar/validar tokens JWT | ~60 |
| [`JwtAuthenticationFilter`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/config/JwtAuthenticationFilter.java) | Filtro HTTP para autenticación JWT | ~80 |
| [`GoogleCloudConfig`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/config/GoogleCloudConfig.java) | Propiedades GCP (Storage, Vertex AI) | ~25 |
| [`VideoRecognitionApplication`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/VideoRecognitionApplication.java) | Clase main Spring Boot | ~10 |
| [`DataInitializer`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/config/DataInitializer.java) | Crea usuario por defecto para pruebas | ~20 |

---

### 🎮 `com.bjj.videorec.controller` (3 clases)

| Clase | Endpoints | Propósito |
|-------|-----------|-----------|
| [`AuthController`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/controller/AuthController.java) | `/api/auth/register`, `/api/auth/login` | Autenticación de usuarios |
| [`VideoController`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/controller/VideoController.java) | `/api/videos/*` | CRUD de videos + trigger análisis |
| [`VideoTagController`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/controller/VideoTagController.java) | `/api/videos/{id}/tags`, `/api/tags/{id}` | CRUD de tags (manuales) |

---

### 📊 `com.bjj.videorec.dto` (8 clases)

#### IA & Análisis
| Clase | Propósito |
|-------|-----------|
| [`TechniqueDetection`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/dto/TechniqueDetection.java) | Detección individual (antes GeminiDetection) |
| [`AnalysisResponse`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/dto/AnalysisResponse.java) | Wrapper respuesta IA (antes GeminiResponse) |

#### Autenticación
| Clase | Propósito |
|-------|-----------|
| [`LoginDto`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/dto/LoginDto.java) | Request de login |
| [`RegisterDto`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/dto/RegisterDto.java) | Request de registro |
| [`AuthResponseDto`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/dto/AuthResponseDto.java) | Response con JWT |

#### Videos & Tags
| Clase | Propósito |
|-------|-----------|
| [`VideoDTO`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/dto/VideoDTO.java) | DTO de video |
| [`VideoTagDTO`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/dto/VideoTagDTO.java) | DTO de tag |
| [`CreateTagRequest`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/dto/CreateTagRequest.java) | Request para crear tag |

---

### 🗄️ `com.bjj.videorec.model` (3 entidades JPA)

| Entidad | Tabla | Relaciones |
|---------|-------|------------|
| [`User`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/model/User.java) | `users` | OneToMany → Video |
| [`Video`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/model/Video.java) | `videos` | ManyToOne → User<br>OneToMany → VideoTag |
| [`VideoTag`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/model/VideoTag.java) | `video_tags` | ManyToOne → Video |

---

### 💾 `com.bjj.videorec.repository` (3 interfaces)

| Repositorio | Extiende | Queries Custom |
|-------------|----------|----------------|
| [`UserRepository`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/repository/UserRepository.java) | JpaRepository | `findByUsername`, `findByEmail` |
| [`VideoRepository`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/repository/VideoRepository.java) | JpaRepository | `findByUserId` |
| [`VideoTagRepository`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/repository/VideoTagRepository.java) | JpaRepository | `findByVideoId`, `findByVideoIdAndSource` |

---

### ⚙️ `com.bjj.videorec.service` (9 clases)

#### Core Business
| Servicio | Responsabilidad |
|----------|----------------|
| [`AuthService`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/service/AuthService.java) | Registro y login |
| [`CustomUserDetailsService`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/service/CustomUserDetailsService.java) | UserDetails para Spring Security |
| [`VideoService`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/service/VideoService.java) | CRUD de videos |
| [`VideoTagService`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/service/VideoTagService.java) | CRUD de tags |

#### AI & Video Analysis ⭐
| Servicio | Responsabilidad | Tipo |
|----------|----------------|------|
| [`AiAnalysisService`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/service/AiAnalysisService.java) | Interfaz genérica para análisis IA | Interface |
| [`SpringAiAnalysisService`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/service/SpringAiAnalysisService.java) | Implementación con Spring AI | Implementación |
| [`BJJPoseDetectionService`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/service/BJJPoseDetectionService.java) | Orquestador de análisis de video | Service |
| [`VideoFrameExtractor`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/service/VideoFrameExtractor.java) | Extracción de frames con ffmpeg | Utility Service |
| [`VideoAnalysisService`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/service/VideoAnalysisService.java) | Punto de entrada para análisis | Orchestrator |

---

### 🛠️ `com.bjj.videorec.util` (1 clase)

| Clase | Propósito | Importancia |
|-------|-----------|-------------|
| [`BJJTechniquePrompt`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/util/BJJTechniquePrompt.java) | Prompt engineering para IA | ⭐ CLAVE |

---

## 🔄 Flujo de Análisis de Video

```
User uploads video
       ↓
VideoController.uploadVideo()
       ↓
VideoService.uploadVideo()
       ↓
VideoAnalysisService.analyzeVideo()
       ↓
BJJPoseDetectionService.analyzeBJJPoses()
       ↓
VideoFrameExtractor.extractFrames() → [frame1.jpg, frame2.jpg, ...]
       ↓
Para cada frame:
   SpringAiAnalysisService.analyzeFrame()
       ↓
   ChatClient.prompt() + BJJTechniquePrompt
       ↓
   AI Model (Gemini/OpenAI/etc.)
       ↓
   AnalysisResponse → List<TechniqueDetection>
       ↓
Consolidar detecciones
       ↓
Crear VideoTag para cada técnica
       ↓
Video.analysisStatus = COMPLETED
```

---

## 📈 Estadísticas del Proyecto

- **Total clases**: 33
- **Líneas de código**: ~5,000 (estimado)
- **Capas arquitectónicas**: 7 (Config, Controller, DTO, Model, Repository, Service, Util)
- **Endpoints REST**: ~10
- **Entidades JPA**: 3
- **Dependencias principales**: Spring Boot, Spring AI, Spring Security, JWT, H2/JPA

---

## 🎯 Clases Más Importantes

### 🥇 Nivel 1 - CRÍTICAS
1. [`SpringAiAnalysisService`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/service/SpringAiAnalysisService.java) - Integración con IA
2. [`BJJPoseDetectionService`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/service/BJJPoseDetectionService.java) - Lógica de detección
3. [`BJJTechniquePrompt`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/util/BJJTechniquePrompt.java) - Prompt engineering

### 🥈 Nivel 2 - IMPORTANTES
4. [`VideoAnalysisService`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/service/VideoAnalysisService.java) - Orquestación
5. [`VideoFrameExtractor`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/service/VideoFrameExtractor.java) - Procesamiento de video
6. [`SecurityConfig`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/config/SecurityConfig.java) - Seguridad
7. [`SpringAiConfig`](file:///home/marcos/Escritorio/bjj-video-recognition-poc/src/main/java/com/bjj/videorec/config/SpringAiConfig.java) - Configuración IA

### 🥉 Nivel 3 - SOPORTE
8. Modelos JPA (User, Video, VideoTag)
9. Controllers (Auth, Video, VideoTag)
10. Servicios de negocio (VideoService, AuthService, etc.)

---

Ver [`code_review_plan.md`](file:///home/marcos/.gemini/antigravity/brain/4e056c7d-4c84-49c7-a549-2221ff57a174/code_review_plan.md) para guía detallada de revisión.
