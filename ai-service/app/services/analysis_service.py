from typing import Any
from pathlib import Path

from app.config import Settings
from app.core.logging import get_logger
from app.schemas.analysis import AnalysisAcceptedResponse, AnalysisRequest, AnalysisResult
from app.services.gemini_enrichment import GeminiEnrichmentService
from app.services.pipeline import VideoAnalysisPipeline
from app.services.video_source import VideoSourceResolver
from app.services.webhook_client import WebhookClient

logger = get_logger(__name__)


class AnalysisService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.video_source_resolver = VideoSourceResolver(settings)
        self.webhook_client = WebhookClient(settings)
        self.pipeline = VideoAnalysisPipeline(settings)
        self.gemini_enrichment = GeminiEnrichmentService(settings)

    def accept_analysis(self, payload: AnalysisRequest) -> AnalysisAcceptedResponse:
        publication_id = int(payload.publication_id)
        logger.info("Accepted analysis request publication_id=%s video_url=%s", publication_id, payload.video_url)
        return AnalysisAcceptedResponse(publication_id=publication_id)

    async def process_analysis_task(self, publication_id: int, payload: AnalysisRequest) -> None:
        logger.info("Processing analysis publication_id=%s", publication_id)
        try:
            video_source = self.video_source_resolver.resolve(payload.video_url)
            result = self.pipeline.analyze(publication_id, payload, video_source)
            if not self.settings.python_parity_mode and not self.settings.spring_poc_enabled:
                result = await self.gemini_enrichment.enrich(video_source, result)
        except Exception as exc:
            logger.exception("Analysis failed publication_id=%s", publication_id)
            result = AnalysisResult(
                publication_id=publication_id,
                status="error",
                frames=[],
                error_message=str(exc),
            )

        await self.webhook_client.send(payload.callback_url, result.to_webhook_payload())

    def health_payload(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "service": "bjj-ai-service",
            "pipeline_mode": "spring_poc_wrapper" if self.settings.spring_poc_enabled else "python_sidecar_wrapper",
            "python_parity_mode": self.settings.python_parity_mode,
            "spring_poc_enabled": self.settings.spring_poc_enabled,
            "spring_poc_base_url": self.settings.spring_poc_base_url,
            "python_sidecar_mode": "subprocess",
            "yolo_model_configured": Path(self.settings.yolo_model_path).exists(),
            "rf_model_configured": Path(self.settings.rf_model_path).exists(),
            "rf_mapping_configured": Path(self.settings.rf_label_mapping_path).exists(),
            "gemini_enabled": self.gemini_enrichment.enabled,
            "gemini_active": self.gemini_enrichment.enabled and not self.settings.python_parity_mode,
        }
