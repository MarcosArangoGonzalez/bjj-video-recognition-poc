# context/poc-architecture.md — Arquitectura real del POC Python
> Cargar en sesiones que tocan el ai-service del POC.
> FUENTE DE VERDAD: python/ — no modificar esa carpeta.

## Pipeline real del POC (python/yolov8_service.py)

```
POST /api/analyze-video (Flask)
  ↓
OpenCV: extraer frames a 2.0 FPS
  ↓ guardar como temp_frames/*.jpg (CRÍTICO para Roboflow)
YOLO: detectar personas → 17 keypoints COCO
  ↓
HybridBJJDetector.hybrid_predict(keypoints, image_path=frame_jpg)
  ├── RF classifier → posición (18 clases ViCoS, 95.6% acc)
  ├── Geometric heuristics → técnicas (Kimura, Armbar, etc.)
  ├── Roboflow API → submissions confirmación (usa image_path)
  └── _detect_transition() → historial 10 frames
  ↓
Majority voting sobre TODOS los frames del vídeo
  ↓
aggregate_combat_story() → bloques con timestamps
  ↓
gemini_master_prompt.py → UNA llamada con el resumen completo
  ↓
JSON final: {frames, combat_story}
```

## Diferencias críticas POC vs ai-service actual

### 1. image_path — LA MÁS IMPORTANTE
POC:     hybrid_predict(keypoints, image_path="temp_frames/frame_001.jpg")
actual:  hybrid_predict(keypoints)  ← SIN image_path → Roboflow desactivado

Sin image_path, HybridBJJDetector no puede llamar a Roboflow.
Roboflow es quien detecta submissions (Kimura, Armbar, etc.).
Sin él, solo hay posiciones RF — por eso el frontend muestra "Standing" sin submissions reales.

### 2. Almacenamiento de frames temporales
POC:    guarda cada frame como JPEG en temp_frames/ antes de llamar al detector
actual: no guarda frames — por eso no puede pasar image_path

### 3. Majority voting
POC:    vota sobre TODOS los frames al final del vídeo
actual: usa temporal buffer de 5-10 frames por ventana deslizante

### 4. Gemini — prompt experto
POC:    gemini_master_prompt.py — prompt largo y experto con contexto BJJ completo
actual: prompt genérico simplificado

### 5. FPS
POC:    2.0 FPS fijo
actual: configurable — verificar que esté en 2.0

## Lo que NO debe cambiar

- python/hybrid_bjj_detector.py — NO tocar
- python/yolov8_service.py — NO tocar (es la referencia)
- python/models/ — NO tocar
- python/gemini_master_prompt.py — copiar, no reescribir

## Regla de paridad

Antes de dar cualquier cambio por bueno:
python test_parity.py --video test_video.mp4
Los detected_class deben coincidir ≥ 90% con el POC.