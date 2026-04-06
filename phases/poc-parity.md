# phases/poc-parity.md — Paridad exacta POC → ai-service
> Cargar con: CLAUDE.md + context/python.md + context/poc-architecture.md
> OBJETIVO: ai-service da resultados idénticos a python/yolov8_service.py
> NO añadir features. NO optimizar. Solo replicar el POC exactamente.

## Diagnóstico confirmado

El ai-service llama a hybrid_predict() SIN image_path.
Sin image_path, Roboflow está desactivado → solo RF + geometría.
Por eso el frontend muestra "Standing + Armbar/Americana" en lugar de
"Side Control + Kimura" como muestra el PDF de referencia.

Causa raíz: ai-service no guarda frames temporales como JPEG,
por lo que no puede pasar image_path al HybridBJJDetector.

## BLOQUE 1 — Leer antes de tocar nada (10 min)

Lee estos ficheros en orden:
1. python/yolov8_service.py — pipeline completo de referencia
2. python/gemini_master_prompt.py — prompt experto de Gemini
3. ai-service/services/inference_service.py — implementación actual
4. ai-service/routers/analysis.py — pipeline actual

Confirmar:
- ¿inference_service.py pasa image_path a hybrid_predict()?
- ¿Dónde guarda los frames temporales (o no los guarda)?
- ¿Cuál es el majority voting actual vs el del POC?
- ¿Qué prompt usa Gemini en el ai-service vs gemini_master_prompt.py?

NO continuar hasta confirmar estas 4 preguntas.

## BLOQUE 2 — Fix crítico: image_path a hybrid_predict (30 min)

### 2.1 Guardar frames temporales en el ai-service

En ai-service/routers/analysis.py o inference_service.py,
replicar exactamente lo que hace python/yolov8_service.py:

```python
import tempfile
import os
import cv2

# Directorio temporal para frames — limpiar al terminar el análisis
temp_dir = tempfile.mkdtemp(prefix="bjj_frames_")

try:
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    ANALYSIS_FPS = 2.0  # CRÍTICO — igual que el POC
    frame_interval = max(1, int(fps / ANALYSIS_FPS))
    
    frame_index = 0
    sampled_index = 0
    all_results = []
    candidate_frames = []  # para Gemini al final
    
    while cap.isOpened():
        ret, frame_bgr = cap.read()
        if not ret:
            break
        
        if frame_index % frame_interval == 0:
            # Guardar frame como JPEG temporal (necesario para Roboflow)
            frame_path = os.path.join(temp_dir, f"frame_{sampled_index:04d}.jpg")
            cv2.imwrite(frame_path, frame_bgr)
            
            # Extraer keypoints con YOLO
            keypoints = yolo_service.detect_poses(frame_bgr)
            
            if keypoints:
                # CRÍTICO: pasar image_path para activar Roboflow
                result = detector.hybrid_predict(keypoints, image_path=frame_path)
                result["timestamp_seconds"] = frame_index / fps
                result["frame_index"] = sampled_index
                all_results.append(result)
                
                # Guardar frame como candidato para Gemini (cada 5 frames)
                if sampled_index % 5 == 0:
                    candidate_frames.append({
                        "frame_bgr": frame_bgr.copy(),
                        "timestamp": frame_index / fps,
                        "result": result
                    })
            
            sampled_index += 1
        
        frame_index += 1
    
    cap.release()

finally:
    # Limpiar frames temporales
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)
```

### 2.2 Majority voting igual que el POC

El POC vota sobre TODOS los frames al final, no por ventana deslizante.
Replicar exactamente:

```python
def apply_majority_voting(results: list) -> list:
    """
    Replica el majority voting de python/yolov8_service.py.
    Vota sobre TODOS los frames — no ventana deslizante.
    La posición ganadora global se usa para resolver ambigüedades.
    """
    if not results:
        return results
    
    from collections import Counter
    
    # Contar todas las posiciones del vídeo completo
    all_positions = [r.get("position", "unknown") for r in results]
    position_counts = Counter(all_positions)
    dominant_position = position_counts.most_common(1)[0][0]
    
    # Estabilizar: si un frame tiene posición con conf < 0.4,
    # reemplazar por la posición dominante del vídeo
    stabilized = []
    for r in results:
        if r.get("position_confidence", 0) < 0.4:
            r = {**r, "position": dominant_position, "stabilized": True}
        stabilized.append(r)
    
    return stabilized
```

## BLOQUE 3 — Gemini: replicar gemini_master_prompt.py (20 min)

### 3.1 Leer python/gemini_master_prompt.py

Copiar el prompt experto EXACTAMENTE.
No reescribir, no simplificar, no "mejorar".
El prompt del POC tiene contexto BJJ específico que es la razón
por la que Gemini da feedback de calidad.

### 3.2 Una llamada al final con el resumen completo

```python
# En ai-service, al final del análisis (después del majority voting):
from services.gemini_service import call_gemini_with_parity

gemini_feedback = await call_gemini_with_parity(
    combat_story=combat_story,
    key_frames=candidate_frames[:3],  # máximo 3 frames
    joint_angles_summary=compute_angles_summary(all_results)
)
```

### 3.3 Throttle correcto (free tier = 15 RPM)

```python
import asyncio, re, time

_last_call = 0.0

async def call_gemini_with_parity(combat_story, key_frames, 
                                   joint_angles_summary) -> str | None:
    global _last_call
    
    # Rate limiting: mínimo 4s entre llamadas (15 RPM = 1 cada 4s)
    elapsed = time.time() - _last_call
    if elapsed < 4.0:
        await asyncio.sleep(4.0 - elapsed)
    
    # Usar el prompt exacto de gemini_master_prompt.py
    from python_compat.gemini_master_prompt import build_gemini_prompt
    prompt = build_gemini_prompt(combat_story, joint_angles_summary)
    
    for attempt in range(3):
        try:
            _last_call = time.time()
            response = model.generate_content([prompt] + encode_key_frames(key_frames))
            return response.text
        except Exception as e:
            if "429" in str(e):
                match = re.search(r"retry in (\d+\.?\d*)s", str(e))
                wait = float(match.group(1)) if match else (2 ** attempt * 5)
                await asyncio.sleep(wait + 1.0)
            else:
                return None
    return None
```

## BLOQUE 4 — Verificar paridad (15 min)

```bash
# 1. Correr POC original en el vídeo de kimura (página 1 del PDF)
cd /home/marcos/Escritorio/bjj-video-recognition-poc-main/python
python yolov8_service.py  # o via Flask: curl POST /api/analyze-video

# 2. Correr ai-service en el mismo vídeo
curl -X POST http://localhost:8081/api/v1/analyze-video \
  -H "Content-Type: application/json" \
  -d '{"publication_id":"test","video_url":"local:kimura_video.mp4",
       "callback_url":"http://localhost:9999/webhook"}'

# 3. Comparar resultados
# POC debe dar: Side Control + Kimura
# ai-service debe dar: Side Control + Kimura
# Si no coinciden, volver al Bloque 2
```

## Ground truth del PDF (referencia de éxito)

| Vídeo | Posición esperada | Técnica esperada | Confianza |
|-------|-------------------|------------------|-----------|
| 1 | Side Control | Kimura | 85-95% |
| 2 | Guard | Triangle Choke | 85-95% |
| 3 | Guard | Triangle → Armbar | 80-85% |
| 4 | Standing Clinch | Lateral Drop | 95-98% |
| 5 | Back Control | Rear Naked Choke | 80-95% |
| 6 | — | Heel Hook | 90% |
| 7 | Turtle | Lapel Choke | 85-95% |
| 8 | Half Guard | Half Guard Sweep | 95% |

Si el ai-service da estos resultados → paridad conseguida.

## Prompt de arranque

```
Lee @CLAUDE.md, @context/python.md, @context/poc-architecture.md
y @phases/poc-parity.md.

OBJETIVO ÚNICO: hacer que ai-service dé los mismos resultados
que python/yolov8_service.py. No añadir features nuevas.

PASO 1 — Lee estos 4 ficheros y confirma las diferencias:
- python/yolov8_service.py
- python/gemini_master_prompt.py
- ai-service/services/inference_service.py
- ai-service/routers/analysis.py

Específicamente confirma:
a) ¿inference_service.py pasa image_path a hybrid_predict()?
b) ¿Guarda frames como JPEG temporales?
c) ¿Usa el mismo majority voting que el POC?
d) ¿Usa el prompt de gemini_master_prompt.py o uno distinto?

PASO 2 — Solo tras mi confirmación, implementa los fixes:
1. Guardar frames como JPEG en temp_dir y pasar image_path a hybrid_predict()
2. Replicar majority voting sobre todos los frames del vídeo
3. Copiar y usar gemini_master_prompt.py exactamente como el POC
4. Limpiar temp_dir al finalizar el análisis

PASO 3 — Test de paridad:
Corre el vídeo de la página 1 del PDF (Kimura from Side Control).
El resultado debe mostrar "Side Control" + "Kimura".
Si no, identifica qué diferencia falta corregir.

No escribas código hasta completar el PASO 1.
```