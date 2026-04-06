# 🚀 AI-Service: FastAPI Refactor Architecture

## Objetivo
Migrar la lógica del PoC (`bjj-video-recognition-poc`) a un microservicio robusto en FastAPI que procese vídeo de forma asíncrona y se comunique con el backend de Java mediante Webhooks.

## Componentes Técnicos
1. **Framework:** FastAPI (Python 3.11+).
2. **Inferencia Local (Primary):**
   - **YOLOv11-pose:** Extracción de 17 keypoints COCO.
   - **Random Forest:** Clasificación de posición base (`bjj_pose_classifier.pkl`).
   - **Geometric Engine:** Lógica de `hybrid_bjj_detector.py` para sumisiones y transiciones.
3. **Jerarquía de Decisión (Deterministic First):**
   - **SUBMISSION** (Prioridad 3): Si la geometría detecta sumisión >= 0.70.
   - **TRANSITION** (Prioridad 2): Cambios de posición/altura detectados.
   - **POSITION** (Prioridad 1): Clasificación del Random Forest.
   - **SCRAMBLE** (Prioridad 0): Fallback por defecto.

## Flujo de Comunicación (Async)
1. Java envía `POST /api/v1/analyze` con `video_url` y `callback_url`.
2. FastAPI responde `202 Accepted` inmediatamente.
3. FastAPI inicia `BackgroundTasks`.
4. Al finalizar, FastAPI envía `POST {callback_url}` con el objeto `CombatStory`.