# 🤝 API Contract: Java ↔ Python

## Input Request (desde Java)
```json
{
  "publication_id": 123,
  "video_url": "http://minio:9000/videos/uuid.mp4",
  "callback_url": "http://backend:8080/api/v1/analysis/webhook"
}

Output Webhook (hacia Java - Slim Payload)

IMPORTANTE: No enviar lista de frames individuales para evitar saturación.
JSON

{
  "publication_id": 123,
  "status": "completed",
  "primary_detected_class": "Armbar",
  "combat_story": [
    {
      "category": "SUBMISSION",
      "technique": "Armbar",
      "label": "Armbar",
      "status": "Secured",
      "description": "Hiperextensión de codo detectada (>160º).",
      "visuals": ["Codo aislado", "Pierna sobre cabeza"],
      "confidence": 0.85,
      "start_timestamp": 12.5
    }
  ]
}