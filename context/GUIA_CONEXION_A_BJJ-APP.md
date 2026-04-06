# Guia de conexion: nuevo ai-service con bjj-app

## Objetivo
Este documento resume como se conectan hoy `bjj-app/backend` (Spring Boot) y `bjj-app/ai-service` (FastAPI), para que puedas levantar un nuevo AI service desde `/Escritorio/bjj-video-recognition-poc-main/python` sin romper el contrato actual.

## Vista rapida de arquitectura
Flujo principal actual:
1. Frontend/subida crea `Publication` con estado `UPLOADED`.
2. Backend recibe `POST /api/v1/analysis/{publicationId}/start` (JWT).
3. Backend cambia estado a `PROCESSING` y despacha async a Python (`POST /api/v1/analyze-video`).
4. AI service procesa en background y devuelve `202` inmediato.
5. Al terminar (ok o error), AI service llama webhook Java `POST /api/v1/analysis/webhook` con header `X-Webhook-Secret`.
6. Backend persiste `frames`, `combat_story`, `primary_detected_class` y deja `Publication` en `COMPLETED` o `ERROR`.

Contrato obligatorio:
- Unico canal de retorno: webhook `POST /api/v1/analysis/webhook`.
- Seguridad webhook: header `X-Webhook-Secret` debe coincidir en ambos lados.

---

## Backend (`/bjj-app/backend`) - ficheros clave

### 1) Entrada/salida de integracion AI
- `backend/src/main/java/es/udc/bjjapp/backend/rest/controllers/AnnotationController.java`
- `backend/src/main/java/es/udc/bjjapp/backend/model/services/AnalysisOrchestratorServiceImpl.java`
- `backend/src/main/java/es/udc/bjjapp/backend/model/services/AiServiceDispatcher.java`
- `backend/src/main/java/es/udc/bjjapp/backend/rest/dtos/PythonCallbackDto.java`
- `backend/src/main/java/es/udc/bjjapp/backend/rest/dtos/DetectedFrameDto.java`
- `backend/src/main/java/es/udc/bjjapp/backend/rest/dtos/JointAnglesDto.java`

Que hace cada uno:
- `AnnotationController`: expone `start` y `webhook`; valida `X-Webhook-Secret` (401 si no coincide).
- `AnalysisOrchestratorServiceImpl`:
  - `startAnalysis(...)`: solo permite estados `UPLOADED` o `ERROR`; marca `PROCESSING`; llama a dispatcher async.
  - `processWebhookResult(...)`: `@Transactional`; gestiona `status=error|completed`; persiste anotaciones y cierra estado.
- `AiServiceDispatcher`: construye JSON para Python y llama `POST {AI_SERVICE_URL}/api/v1/analyze-video`.

### 2) Seguridad y reglas de acceso
- `backend/src/main/java/es/udc/bjjapp/backend/rest/common/SecurityConfig.java`
- `backend/src/main/java/es/udc/bjjapp/backend/rest/common/JwtFilter.java`

Detalles:
- `/api/v1/analysis/webhook` esta `permitAll()` por JWT, pero protegido por `X-Webhook-Secret`.
- `JwtFilter` ignora JWT en webhook porque usa autenticacion por secret compartido.

### 3) Configuracion de integracion
- `backend/src/main/resources/application.yml`

Propiedades clave:
- `project.ai-service.url` (env: `AI_SERVICE_URL`)
- `project.ai-service.callback-url` (env: `AI_CALLBACK_URL`)
- `project.ai-service.webhook-secret` (env: `AI_WEBHOOK_SECRET`)
- `project.ai-service.internal-secret` (env: `AI_INTERNAL_SECRET`) - para endpoints internos de flywheel

### 4) Entidad impactada por el webhook
- `backend/src/main/java/es/udc/bjjapp/backend/model/entities/Publication.java`

Campos relevantes:
- `status`: `UPLOADED | PROCESSING | COMPLETED | ERROR`
- `primaryDetectedClass`
- `combatStory` (JSONB)
- `vectorized` (phase 5C)

### 5) Endpoints internos opcionales (flywheel)
- `backend/src/main/java/es/udc/bjjapp/backend/rest/controllers/InternalController.java`

Endpoints:
- `GET /api/v1/publications/vectorization-pending` (requiere `X-Internal-Secret`)
- `PATCH /api/v1/publications/{id}/vectorized` (requiere `X-Internal-Secret`)

Esto es opcional para conectar analisis basico, pero necesario si replicas vectorizacion automatica.

---

## AI Service (`/bjj-app/ai-service`) - ficheros clave

### 1) App y arranque
- `ai-service/main.py`
- `ai-service/config.py`

Que aportan:
- `main.py`: inicializa servicios (YOLO, RF, Geometry, RAG, Agent, Flywheel), expone health y routers.
- `config.py`: settings de entorno (Gemini, webhook secret, callback Java, modelos, etc).

### 2) API de analisis y callback
- `ai-service/routers/analysis.py`
- `ai-service/models/schemas.py`

Contrato API entrada (backend -> ai-service):
- Endpoint: `POST /api/v1/analyze-video`
- DTO: `AnalysisRequest`
- Respuesta: `202 Accepted` inmediata + procesamiento en background

Contrato callback salida (ai-service -> backend):
- Funcion: `_send_webhook_callback(...)`
- Header: `X-Webhook-Secret: <AI_WEBHOOK_SECRET>`
- Payload: `WebhookPayload` con:
  - `publication_id`
  - `status` (`completed` o `error`)
  - `frames` (opcional si error)
  - `error_message` (si error)
  - `combat_story` (opcional)
  - `primary_detected_class` (opcional)

### 3) Servicios de pipeline
- `ai-service/services/yolo_service.py`
- `ai-service/services/rf_position_service.py`
- `ai-service/services/geometry_service.py`
- `ai-service/services/gemini_vision_service.py`
- `ai-service/services/rag_service.py`
- `ai-service/services/agent_service.py`
- `ai-service/services/flywheel_service.py`
- `ai-service/services/roboflow_technique_service.py`

Pipeline resumido en `routers/analysis.py`:
- Video -> YOLO pose -> RF posicion -> geometria -> reglas/fusion -> feedback -> webhook Java.
- Regla importante: aunque fallen frames o LLM, se intenta enviar webhook igualmente.

### 4) Configuracion de entorno AI
- `ai-service/.env`
- `ai-service/.env.example`

Variables practicas de integracion:
- `AI_WEBHOOK_SECRET` (debe coincidir con backend)
- `AI_INTERNAL_SECRET` (si usas flywheel interno)
- `JAVA_CALLBACK_URL` (URL del webhook Java)
- `LOCAL_STORAGE_DIR` (path compartido para `local:<filename>`)

---

## Contrato de datos exacto (minimo obligatorio)

## Request que backend envia al nuevo ai-service
Endpoint: `POST {AI_SERVICE_URL}/api/v1/analyze-video`

```json
{
  "publication_id": "123",
  "video_url": "local:video_123.mp4",
  "callback_url": "http://backend:8080/api/v1/analysis/webhook",
  "user_belt": "white",
  "auto_tag": true,
  "biometric_tracking": false
}
```

Notas:
- `publication_id` llega como string desde Java.
- `video_url` acepta `http(s)` o formato `local:<filename>`.
- Tu nuevo servicio debe responder `202` rapido y procesar asincrono.

## Callback que el nuevo ai-service debe enviar al backend
Endpoint: `POST /api/v1/analysis/webhook` del backend
Header obligatorio:
- `X-Webhook-Secret: <mismo valor que AI_WEBHOOK_SECRET en backend>`

Ejemplo exito:
```json
{
  "publication_id": 123,
  "status": "completed",
  "frames": [
    {
      "frame_index": 10,
      "timestamp_seconds": 0.33,
      "detected_class": "mount",
      "confidence": 0.91,
      "joint_angles": {
        "left_elbow_angle": 155.0,
        "right_elbow_angle": 148.2,
        "left_knee_angle": 92.0,
        "right_knee_angle": 88.1,
        "hip_spine_angle": 42.7,
        "spine_tilt_angle": 11.3
      },
      "feedback": "Control de cadera correcto.",
      "suggested_tags": [{"tag": "mount", "confidence": 0.91}],
      "player_role": "ATTACKER_TOP"
    }
  ],
  "combat_story": [
    {
      "category": "POSITION",
      "technique": "mount",
      "label": "mount",
      "status": "Secured",
      "description": "Top control established",
      "visuals": ["Hip pressure"],
      "confidence": 91,
      "start_timestamp": 0.0,
      "duration": 3.0
    }
  ],
  "primary_detected_class": "mount"
}
```

Ejemplo error:
```json
{
  "publication_id": 123,
  "status": "error",
  "error_message": "Failed to open video source",
  "frames": []
}
```

---

## Flujo de datos end-to-end (detallado)
1. Usuario sube/publica video.
2. `PublicationController` crea `Publication` con `status=UPLOADED`.
3. Cliente invoca `POST /api/v1/analysis/{id}/start`.
4. `AnalysisOrchestratorServiceImpl.startAnalysis(...)` valida estado y pasa a `PROCESSING`.
5. `AiServiceDispatcher.dispatch(...)` envia `AnalysisRequest` al AI service.
6. AI service responde `202` y lanza tarea de fondo.
7. AI service procesa frames y construye `frames/combat_story/primary_detected_class`.
8. AI service llama webhook Java con `X-Webhook-Secret`.
9. `AnnotationController.handleWebhook(...)` valida secret.
10. `processWebhookResult(...)`:
   - si `status=error` -> `Publication.ERROR`
   - si `status=completed` -> persiste `Annotation` por frame, `combatStory`, `primaryDetectedClass` y marca `COMPLETED`.

---

## Despliegue actual y punto fino importante
En `docker-compose.yml` de este repo:
- servicio `ai-service` local esta comentado.
- backend usa `AI_SERVICE_URL: http://host.docker.internal:8081`.

Implicacion:
- hoy backend esta cableado para un AI service externo (PoC en `:8081`), no para `bjj-app/ai-service` (`:8082`).

Si vas a conectar tu nuevo servicio, revisa al menos:
- `AI_SERVICE_URL`
- `AI_CALLBACK_URL`
- `AI_WEBHOOK_SECRET`
- red/hostname (localhost, backend, host.docker.internal)

---

## Checklist de conexion para tu nuevo ai-service (desde el PoC)
1. Implementa en el nuevo servicio el endpoint `POST /api/v1/analyze-video` con body snake_case compatible.
2. Devuelve `202` inmediata y ejecuta procesamiento en background.
3. Implementa callback a `callback_url` con payload compatible `PythonCallbackDto`.
4. Envia siempre header `X-Webhook-Secret`.
5. Garantiza que en caso de excepcion tambien se envia webhook con `status=error`.
6. Respeta `auto_tag` y `biometric_tracking` al construir `frames`.
7. Alinea variables de entorno entre backend y nuevo servicio.
8. Verifica conectividad de volumen si usas `video_url=local:<filename>`.
9. Prueba humo:
   - start analysis devuelve 202
   - backend pasa a `PROCESSING`
   - llega webhook
   - backend termina en `COMPLETED` o `ERROR` sin quedarse en `PROCESSING`

---

## Preparacion para integracion futura con RAG (RAG-ready)
Ademas de conectarse al backend, el nuevo ai-service debe nacer con contrato estable para activar RAG sin romper API.

### 1) Interfaces que debes mantener desde ya
- Mantener `feedback` por frame en `DetectedFrameDto` (aunque inicialmente sea heuristico o `null`).
- Mantener `combat_story` y `primary_detected_class` en webhook (base para vectorizacion y retrieval contextual).
- Mantener `suggested_tags` (sirve para enriquecer chunks y filtros semanticos).

### 2) Estructura minima de modulos en el nuevo servicio
- `services/rag_service.py`: capa de retrieval/embeddings (aunque quede en modo stub al principio).
- `services/agent_service.py`: capa de generacion de feedback que pueda funcionar en modo `heuristic` o `rag`.
- `scripts/populate_chroma.py` (o equivalente): carga inicial de conocimiento.
- `knowledge/`: documentos fuente y/o chunks semilla.

Objetivo: desacoplar pipeline de vision y pipeline de lenguaje para que activar RAG sea cambiar configuracion, no reescribir flujo.

### 3) Variables de entorno recomendadas (aunque no actives RAG aun)
Define estas claves en `.env` desde el inicio:
- `AGENT_ENABLED=true|false`
- `GEMINI_API_KEY=...`
- `EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2`
- `EMBEDDING_DIMENSION=384`
- `CHROMA_PERSIST_DIR=./data/chroma_db`
- `RAG_RETRIEVAL_K=3`

Con esto puedes arrancar sin RAG (modo heuristico) y activarlo despues sin tocar contrato backend.

### 4) Datos que deben quedar listos para vectorizacion futura
Cuando cierres cada analisis, procura persistir o exponer al menos:
- `publication_id`
- `primary_detected_class`
- `combat_story` (bloques con `technique`, `position/category`, `confidence`, `start_timestamp`, `duration`)
- `suggested_tags`

Estos campos son la materia prima para generar chunks de calidad en el flywheel.

### 5) Endpoints internos para flywheel (opcional ahora, recomendable)
Si quieres dejarlo preparado para Phase 5C/6:
- Consumir en backend: `GET /api/v1/publications/vectorization-pending`
- Confirmar en backend: `PATCH /api/v1/publications/{id}/vectorized`
- Autenticacion interna: `X-Internal-Secret`

Aunque no lo uses ya, diseniar el nuevo servicio con este adaptador evita deuda tecnica.

### 6) Modo de operacion recomendado por fases
1. Fase A: `heuristic-only` (sin RAG, pero con contrato completo de salida).
2. Fase B: `hybrid` (retrieval activo en subset de frames/eventos).
3. Fase C: `rag-first` (feedback guiado por retrieval + fallback heuristico).

Regla clave: nunca romper el webhook ni el schema de callback al cambiar de modo.

---

## Comandos utiles de validacion

### 1) Health backend
```bash
curl -i http://localhost:8080/api/v1/health
```

### 2) Health ai-service
```bash
curl -i http://localhost:8082/health
```

### 3) Simular webhook manual (debug rapido)
```bash
curl -i -X POST "http://localhost:8080/api/v1/analysis/webhook" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: dev-secret-change-in-prod" \
  -d '{
    "publication_id": 123,
    "status": "error",
    "error_message": "manual test"
  }'
```

Si devuelve `401`, revisa inmediatamente el valor de `AI_WEBHOOK_SECRET` en ambos lados.

---

## Minimo que NO puedes romper
- No cambiar nombre de campos snake_case en request/callback.
- No quitar `X-Webhook-Secret`.
- No devolver solo sync sin callback.
- No dejar publicaciones en `PROCESSING` sin webhook final.
- No introducir un canal alternativo de retorno distinto al webhook.
