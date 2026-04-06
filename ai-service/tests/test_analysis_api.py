import asyncio

from fastapi import BackgroundTasks

from app.config import Settings
from app.routers.analysis import analyze_video
from app.schemas.analysis import AnalysisRequest
from app.services.analysis_service import AnalysisService
from main import create_app


def test_analyze_video_accepts_request_and_registers_background_task(monkeypatch):
    settings = Settings(
        yolo_model_path="./missing-model.pt",
        rf_model_path="./missing-rf.pkl",
        rf_label_mapping_path="./missing-mapping.json",
    )
    service = AnalysisService(settings)
    payload = AnalysisRequest(
        publication_id="123",
        video_url="http://example.com/video.mp4",
        callback_url="http://backend/api/v1/analysis/webhook",
    )
    background_tasks = BackgroundTasks()
    captured = {}

    def fake_process(publication_id, request_payload):
        captured["publication_id"] = publication_id
        captured["callback_url"] = request_payload.callback_url

    monkeypatch.setattr(service, "process_analysis_task", fake_process)
    response = asyncio.run(analyze_video(payload, background_tasks, service))
    for task in background_tasks.tasks:
        task.func(*task.args, **task.kwargs)

    assert response.model_dump() == {"status": "accepted", "publication_id": 123}
    assert captured == {
        "publication_id": 123,
        "callback_url": "http://backend/api/v1/analysis/webhook",
    }


def test_health_route_exists():
    app = create_app()
    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/api/v1/analyze-video" in paths
