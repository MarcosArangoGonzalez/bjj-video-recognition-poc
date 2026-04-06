import asyncio

import httpx
import pytest

from app.config import Settings
from app.schemas.analysis import AnalysisRequest, WebhookPayload
from app.services.video_source import VideoSourceResolver
from app.services.webhook_client import WebhookClient


def test_resolve_local_video(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_text("test", encoding="utf-8")
    resolver = VideoSourceResolver(Settings(local_storage_dir=str(tmp_path)))
    assert resolver.resolve("local:video.mp4") == str(video)


def test_resolve_invalid_scheme():
    resolver = VideoSourceResolver(Settings())
    with pytest.raises(ValueError):
        resolver.resolve("ftp://unsupported")


def test_webhook_client_sends_secret_header(monkeypatch):
    captured = {}
    settings = Settings(ai_webhook_secret="shared-secret", webhook_max_retries=0)
    client = WebhookClient(settings)

    async def fake_post(self, url, json, headers):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return httpx.Response(204, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    payload = WebhookPayload(publication_id=1, status="completed", frames=[], primary_detected_class="mount")
    asyncio.run(client.send("http://backend/api/v1/analysis/webhook", payload))

    assert captured["headers"]["X-Webhook-Secret"] == "shared-secret"
    assert captured["json"]["primary_detected_class"] == "mount"


def test_analysis_request_coerces_numeric_publication_id():
    payload = AnalysisRequest(
        publication_id="123",
        video_url="http://example.com/video.mp4",
        callback_url="http://backend/api/v1/analysis/webhook",
    )
    assert payload.publication_id == "123"
