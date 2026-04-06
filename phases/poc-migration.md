# phases/poc-migration.md — Migrar Flask POC → FastAPI ai-service
> Cargar con: CLAUDE.md + context/python.md
> Proyecto: bjj-video-recognition-poc-main
> Objetivo: reemplazar bjj-app/ai-service con el motor del POC que funciona bien

## Contexto
bjj-app/ai-service tiene buena arquitectura pero baja precisión.
bjj-video-recognition-poc-main/python/ tiene el motor de detección real que funciona.
El plan: montar FastAPI sobre el motor del POC, manteniendo el contrato con Java.

## Estructura objetivo
```
bjj-video-recognition-poc-main/
├── python/                          # motor existente — NO TOCAR
│   ├── hybrid_bjj_detector.py       # cerebro táctico — NO TOCAR
│   ├── models/
│   │   ├── bjj_custom.pt            # YOLOv8-pose
│   │   ├── bjj_pose_classifier.pkl  # RF 18 clases
│   │   └── label_mapping.json
│   └── yolov8_service.py            # referencia de paridad
└── ai-service/                      # NUEVO — FastAPI wrapper
    ├── main.py
    ├── requirements.txt
    ├── schemas/
    │   └── analysis.py
    ├── routers/
    │   └── analysis.py
    └── services/
        ├── inference_service.py
        └── hybrid_bjj_detector.py   # copia de python/
```

## Contrato Java — no romper nunca
POST /api/v1/analyze-video → 202 Accepted inmediato
Body entrada:
{
  "publication_id": "61",
  "video_url": "local:uuid.mp4",
  "callback_url": "http://backend:8080/api/v1/analysis/webhook",
  "user_belt": "white"
}

Webhook salida → Java:
Header: X-Webhook-Secret: {AI_WEBHOOK_SECRET}
Body:
{
  "publication_id": 61,
  "status": "completed",
  "frames": [...DetectedFrameDto],
  "combat_story": [...CombatBlockDto],
  "error_message": null
}

DetectedFrameDto campos (snake_case — Java tiene @JsonProperty):
  frame_index, timestamp_seconds, detected_class, confidence,
  joint_angles, feedback, suggested_tags, player_role

JointAngles campos:
  left_elbow_angle, right_elbow_angle, left_knee_angle,
  right_knee_angle, hip_spine_angle, spine_tilt_angle

CombatBlockDto campos:
  label, start, end, duration, peak_confidence

## BLOQUE 1 — Verificar estructura existente del ai-service del POC

Antes de escribir código, leer:
1. /bjj-video-recognition-poc-main/ai-service/main.py
2. /bjj-video-recognition-poc-main/ai-service/routers/analysis.py
3. /bjj-video-recognition-poc-main/ai-service/services/inference_service.py
4. /bjj-video-recognition-poc-main/ai-service/schemas/analysis.py
5. /bjj-video-recognition-poc-main/python/hybrid_bjj_detector.py (referencia)

Identificar qué falta para cumplir el contrato Java completo.

## BLOQUE 2 — Webhook con X-Webhook-Secret

El bug crítico del sistema anterior era 401 en el webhook.
Verificar que _send_webhook_callback() en routers/analysis.py hace:

```python
import os
import httpx

WEBHOOK_SECRET = os.environ.get("AI_WEBHOOK_SECRET", "dev-secret-change-in-prod")

async def _send_webhook_callback(callback_url, publication_id, status,
                                  frames=None, combat_story=None, error=None):
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Secret": WEBHOOK_SECRET  # CRÍTICO — sin esto → 401
    }
    payload = {
        "publication_id": int(publication_id),
        "status": status,
        "frames": frames,
        "combat_story": combat_story,
        "error_message": error
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(callback_url, json=payload, headers=headers)
        resp.raise_for_status()
```

## BLOQUE 3 — CombatStoryAggregator

Función que agrupa frames en bloques de posición/técnica:

```python
from collections import deque

def aggregate_combat_story(frames: list, fps: float = 2.0) -> list:
    """
    Agrupa frames consecutivos en bloques con duración mínima 0.5s.
    Bloques < 0.5s se absorben en el anterior (anti-flicker).
    """
    if not frames:
        return []

    MIN_BLOCK_DURATION = 0.5
    blocks = []
    current_label = frames[0].get("detected_class", "unknown")
    current_start = frames[0].get("timestamp_seconds", 0.0)
    current_peak_conf = frames[0].get("confidence", 0.0)

    for frame in frames[1:]:
        label = frame.get("detected_class", "unknown")
        ts = frame.get("timestamp_seconds", 0.0)
        conf = frame.get("confidence", 0.0)

        if label == current_label:
            current_peak_conf = max(current_peak_conf, conf)
        else:
            duration = ts - current_start
            if duration >= MIN_BLOCK_DURATION:
                blocks.append({
                    "label": _clean_label(current_label),
                    "start": round(current_start, 2),
                    "end": round(ts, 2),
                    "duration": round(duration, 2),
                    "peak_confidence": round(current_peak_conf, 3)
                })
            elif blocks:
                blocks[-1]["end"] = round(ts, 2)
                blocks[-1]["duration"] = round(
                    ts - blocks[-1]["start"], 2)

            current_label = label
            current_start = ts
            current_peak_conf = conf

    return blocks

def _clean_label(label: str) -> str:
    """Convierte etiquetas técnicas a nombres legibles."""
    LABELS = {
        "side_control1": "Side Control", "side_control2": "Side Control",
        "mount1": "Mount", "mount2": "Mount",
        "back1": "Back Control", "back2": "Back Control",
        "closed_guard1": "Closed Guard", "closed_guard2": "Closed Guard",
        "open_guard1": "Open Guard", "open_guard2": "Open Guard",
        "half_guard1": "Half Guard", "half_guard2": "Half Guard",
        "5050_guard": "50/50 Guard",
        "turtle1": "Turtle", "turtle2": "Turtle",
        "standing": "Standing",
        "takedown1": "Takedown", "takedown2": "Takedown",
        "scramble": "Scramble",
        "armbar": "Armbar", "kimura": "Kimura",
        "triangle_choke": "Triangle Choke",
        "rear_naked_choke": "Rear Naked Choke",
        "heel_hook": "Heel Hook",
    }
    return LABELS.get(label, label.replace("_", " ").title())
```

## BLOQUE 4 — Gemini throttling correcto

Free tier = 15 RPM. Con asyncio.Semaphore(2) + delay 1s máximo 2 llamadas/seg = 120 RPM → excede limit.

Configuración correcta para free tier:
```python
import asyncio
import time

_last_gemini_call = 0.0
_GEMINI_MIN_INTERVAL = 4.0  # 60s / 15 RPM = 4s entre llamadas

async def call_gemini_with_throttle(prompt: str) -> str | None:
    global _last_gemini_call
    now = time.time()
    elapsed = now - _last_gemini_call
    if elapsed < _GEMINI_MIN_INTERVAL:
        await asyncio.sleep(_GEMINI_MIN_INTERVAL - elapsed)
    _last_gemini_call = time.time()
    # ... llamada a Gemini
```

Alternativa más simple: llamar a Gemini solo en el aggregator final
(1 llamada por vídeo para generar el feedback del combat_story completo)
en lugar de por frame. Esto usa 1 RPM independientemente del vídeo.

## BLOQUE 5 — Variables de entorno

Crear ai-service/.env.example:
```
AI_WEBHOOK_SECRET=dev-secret-change-in-prod
GEMINI_API_KEY=your-gemini-api-key
GEMINI_ENABLED=true
ANALYSIS_FPS=2.0
PORT=8081
```

Verificar que docker-compose.yml del POC tiene:
```yaml
ai-service:
  environment:
    - AI_WEBHOOK_SECRET=${AI_WEBHOOK_SECRET}
    - GEMINI_API_KEY=${GEMINI_API_KEY}
```

Y que Java (bjj-app) tiene:
```yaml
backend:
  environment:
    - PROJECT_AI_SERVICE_URL=http://ai-service:8081
    - PROJECT_AI_SERVICE_WEBHOOK_SECRET=${AI_WEBHOOK_SECRET}
```

## BLOQUE 6 — Test de paridad

Verificar que el nuevo ai-service da los mismos resultados que python/yolov8_service.py:

```bash
# Correr ambos sobre el mismo frame y comparar
cd /bjj-video-recognition-poc-main

# Referencia (Flask/POC original)
python python/yolov8_service.py --frame test_frame.jpg

# Nuevo (FastAPI)
curl -X POST http://localhost:8081/api/analyze-frame \
  -F "file=@test_frame.jpg" | python3 -m json.tool

# Los detected_class deben coincidir en > 90% de los frames
```

## BLOQUE 7 — Integración con bjj-app Java

Para usar este ai-service con el backend Java existente:

1. En bjj-app/docker-compose.yml, apuntar al nuevo servicio:
```yaml
PROJECT_AI_SERVICE_URL=http://poc-ai-service:8081
```

2. Verificar en Java SecurityConfig.java:
```java
.requestMatchers("/api/v1/analysis/webhook").permitAll()
// Sin JWT — el secret va en X-Webhook-Secret header
```

3. Verificar en Java AnnotationController o WebhookController:
```java
@PostMapping("/api/v1/analysis/webhook")
public ResponseEntity<Void> receiveWebhook(
    @RequestHeader("X-Webhook-Secret") String secret,
    @RequestBody WebhookPayload payload) {
    if (!webhookSecret.equals(secret)) return ResponseEntity.status(401).build();
    // procesar...
}
```

## Checklist de verificación

### Pipeline
- [ ] POST /api/v1/analyze-video → 202 en < 100ms
- [ ] Background task completa análisis
- [ ] Webhook llega a Java con X-Webhook-Secret ✅ (no 401)
- [ ] Java marca publicación como COMPLETED
- [ ] combat_story tiene bloques con labels limpios ("Mount" no "mount1")

### Precisión
- [ ] Frame de mount → "Mount" con conf > 0.7
- [ ] Frame de side control → "Side Control"
- [ ] Frame de armbar (codo > 160°) → "Armbar"
- [ ] Frame de scramble → "Scramble" (no técnica inventada)

### Gemini
- [ ] Sin errores 429 (throttle 4s entre llamadas)
- [ ] Feedback coherente con la técnica detectada
- [ ] Si Gemini falla → pipeline continúa con feedback heurístico
