# context/python.md — Reglas Python AI Service (POC)
> Solo cargar en sesiones que modifican código Python.
> Proyecto activo: bjj-video-recognition-poc-main
> Motor de referencia: python/hybrid_bjj_detector.py y python/yolov8_service.py
> El ai-service es un wrapper FastAPI sobre ese motor — NO reemplaza la lógica.

---

## Estructura del proyecto

```
bjj-video-recognition-poc-main/
├── python/                          # Motor táctico — FUENTE DE VERDAD
│   ├── hybrid_bjj_detector.py       # cerebro — NO modificar lógica
│   ├── yolov8_service.py            # referencia de paridad
│   ├── models/
│   │   ├── bjj_custom.pt            # YOLOv8-pose
│   │   ├── bjj_pose_classifier.pkl  # RF 18 clases ViCoS
│   │   └── label_mapping.json
│   └── re_extract_features.py
└── ai-service/                      # Wrapper FastAPI
    ├── main.py
    ├── config.py
    ├── requirements.txt
    ├── schemas/analysis.py
    ├── routers/analysis.py
    └── services/
        ├── inference_service.py     # wraps hybrid_bjj_detector
        └── hybrid_bjj_detector.py  # copia de python/ — mantener en sync
```

---

## Regla crítica de paridad

El ai-service DEBE dar resultados idénticos a python/yolov8_service.py.
Antes de cualquier cambio, verificar que no rompe la paridad.
Si hay duda entre "mejor arquitectura" y "mismo resultado que el POC",
siempre gana el mismo resultado que el POC.

Parámetros que DEBEN coincidir exactamente con el POC:
- ANALYSIS_FPS = 2.0  (el POC usa 2fps — no cambiar)
- Majority voting: misma ventana de frames que el POC
- Umbrales de confianza: los mismos que hybrid_bjj_detector.py
- Orden de llamadas: YOLO → RF → Geometría → (Gemini al final)

---

## Config — nunca hardcodear secrets

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    gemini_api_key: str = ""
    ai_webhook_secret: str = "dev-secret-change-in-prod"
    gemini_enabled: bool = True
    analysis_fps: float = 2.0      # CRÍTICO — no cambiar sin paridad test
    port: int = 8081

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## Contrato webhook Python → Java

Header obligatorio — sin esto Java devuelve 401:
```python
headers = {
    "Content-Type": "application/json",
    "X-Webhook-Secret": settings.ai_webhook_secret  # CRÍTICO
}
```

Payload (snake_case — Java tiene @JsonProperty):
```python
class JointAngles(BaseModel):
    left_elbow_angle:  float | None = None
    right_elbow_angle: float | None = None
    left_knee_angle:   float | None = None
    right_knee_angle:  float | None = None
    hip_spine_angle:   float | None = None
    spine_tilt_angle:  float | None = None

class DetectedFrameDto(BaseModel):
    frame_index:        int
    timestamp_seconds:  float
    detected_class:     str
    confidence:         float
    joint_angles:       JointAngles
    feedback:           str | None = None
    suggested_tags:     list | None = None
    player_role:        str | None = None

class CombatBlockDto(BaseModel):
    label:            str
    start:            float
    end:              float
    duration:         float
    peak_confidence:  float
    gemini_feedback:  str | None = None  # solo en el primer bloque

class WebhookPayload(BaseModel):
    publication_id:  int
    status:          str   # "completed" | "error"
    frames:          list[DetectedFrameDto] | None = None
    combat_story:    list[CombatBlockDto] | None = None
    error_message:   str | None = None
```

---

## Gemini — una llamada por vídeo

NUNCA llamar a Gemini dentro del bucle de frames.
UNA sola llamada al finalizar con el combat_story completo:

```python
import asyncio
import re
import base64
import cv2

async def call_gemini_single(
    combat_story: list,
    joint_angles_summary: dict,
    key_frames_bgr: list  # máximo 3 frames OpenCV
) -> str | None:
    """Una sola llamada multimodal por vídeo. Máximo 3 reintentos."""
    if not settings.gemini_enabled or not settings.gemini_api_key:
        return None

    story_text = " → ".join(
        f"{b['label']} ({b['duration']}s, {b['peak_confidence']:.0%})"
        for b in combat_story
    )
    angles_text = (
        f"L.elbow: {joint_angles_summary.get('left_elbow_mean','?')}° "
        f"R.elbow: {joint_angles_summary.get('right_elbow_mean','?')}° "
        f"L.knee:  {joint_angles_summary.get('left_knee_mean','?')}°"
    )
    prompt = f"""Expert BJJ coach analyzing a sparring clip.

Sequence detected: {story_text}
Joint angles (avg): {angles_text}

Review the key frames and provide expert coaching feedback:
- Confirm or correct the detected techniques
- Identify the most critical technical error
- Give one specific actionable improvement

Be specific about BJJ mechanics. 3-4 sentences."""

    content = [prompt]
    for frame_bgr in key_frames_bgr[:3]:
        _, buf = cv2.imencode('.jpg', frame_bgr,
                              [cv2.IMWRITE_JPEG_QUALITY, 85])
        content.append({
            "mime_type": "image/jpeg",
            "data": base64.b64encode(buf).decode()
        })

    for attempt in range(3):
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.gemini_api_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(content)
            return response.text
        except Exception as e:
            err = str(e)
            if "429" in err:
                # Leer tiempo de espera del mensaje de error
                match = re.search(r"retry in (\d+\.?\d*)s", err)
                wait = float(match.group(1)) if match else (2 ** attempt * 5)
                await asyncio.sleep(wait + 1.0)
            else:
                return None  # Error no recuperable
    return None  # Agotados reintentos → fallback heurístico
```

---

## CombatStoryAggregator

```python
def aggregate_combat_story(frames: list) -> list:
    """Agrupa frames en bloques. Mínimo 0.5s por bloque."""
    if not frames:
        return []

    LABEL_MAP = {
        "side_control1": "Side Control", "side_control2": "Side Control",
        "mount1": "Mount",               "mount2": "Mount",
        "back1": "Back Control",         "back2": "Back Control",
        "closed_guard1": "Closed Guard", "closed_guard2": "Closed Guard",
        "open_guard1": "Open Guard",     "open_guard2": "Open Guard",
        "half_guard1": "Half Guard",     "half_guard2": "Half Guard",
        "5050_guard": "50/50 Guard",
        "turtle1": "Turtle",             "turtle2": "Turtle",
        "standing": "Standing",
        "takedown1": "Takedown",         "takedown2": "Takedown",
        "scramble": "Scramble",
        "armbar": "Armbar",              "kimura": "Kimura",
        "triangle_choke": "Triangle Choke",
        "rear_naked_choke": "Rear Naked Choke",
        "heel_hook": "Heel Hook",
    }

    blocks = []
    cur_label = frames[0].get("detected_class", "unknown")
    cur_start = frames[0].get("timestamp_seconds", 0.0)
    cur_peak  = frames[0].get("confidence", 0.0)

    for frame in frames[1:]:
        label = frame.get("detected_class", "unknown")
        ts    = frame.get("timestamp_seconds", 0.0)
        conf  = frame.get("confidence", 0.0)

        if label == cur_label:
            cur_peak = max(cur_peak, conf)
        else:
            dur = ts - cur_start
            if dur >= 0.5:
                blocks.append({
                    "label":           LABEL_MAP.get(cur_label,
                                           cur_label.replace("_"," ").title()),
                    "start":           round(cur_start, 2),
                    "end":             round(ts, 2),
                    "duration":        round(dur, 2),
                    "peak_confidence": round(cur_peak, 3),
                    "gemini_feedback": None
                })
            elif blocks:
                blocks[-1]["end"]      = round(ts, 2)
                blocks[-1]["duration"] = round(ts - blocks[-1]["start"], 2)
            cur_label = label
            cur_start = ts
            cur_peak  = conf

    return blocks


def select_key_frames(candidate_frames: list, combat_story: list) -> list:
    """1 frame de mayor confianza por bloque del combat_story."""
    key_frames = []
    for block in combat_story[:5]:
        block_frames = [
            f for f in candidate_frames
            if block["start"] <= f.get("timestamp_seconds", 0) <= block["end"]
            and f.get("frame_bgr") is not None
        ]
        if block_frames:
            best = max(block_frames, key=lambda f: f.get("confidence", 0))
            key_frames.append(best["frame_bgr"])
    return key_frames
```

---

## Manejo de errores — pipeline nunca se rompe

```python
# Nunca propagar excepción fuera del frame
for frame_data in sampled_frames:
    try:
        result = detector.hybrid_predict(keypoints, image_path)
    except Exception as e:
        logger.error(f"Frame failed: {e}")
        result = {"position": "unknown", "confidence": 0.0}

# Gemini falla → webhook se envía igualmente con feedback=None
try:
    gemini_feedback = await call_gemini_single(story, angles, key_frames)
    if story and gemini_feedback:
        story[0]["gemini_feedback"] = gemini_feedback
except Exception as e:
    logger.error(f"Gemini final call failed: {e}")
    # continuar sin feedback
```

---

## Variables de entorno (.env.example)

```
AI_WEBHOOK_SECRET=dev-secret-change-in-prod
GEMINI_API_KEY=your-gemini-api-key
GEMINI_ENABLED=true
ANALYSIS_FPS=2.0
PORT=8081
```

---

## Test de paridad — ejecutar antes de cualquier PR

```bash
# Ground truth del POC
cd python
python yolov8_service.py --video ../test_video.mp4 > poc_output.json

# ai-service
curl -s -X POST http://localhost:8081/api/v1/analyze-video \
  -H "Content-Type: application/json" \
  -d '{"publication_id":"99","video_url":"local:test_video.mp4",
       "callback_url":"http://localhost:9999/webhook"}' 
# esperar webhook → guardar como aiservice_output.json

# Comparar detected_class frame a frame
python compare_outputs.py poc_output.json aiservice_output.json
# Objetivo: ≥ 90% coincidencia en detected_class
```