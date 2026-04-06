import asyncio

import httpx

from app.config import Settings
from app.core.logging import get_logger
from app.schemas.analysis import WebhookPayload

logger = get_logger(__name__)


class WebhookClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        secret = settings.ai_webhook_secret or ""
        preview = f"{secret[:4]}..." if secret else "<empty>"
        logger.info("Webhook secret loaded prefix=%s", preview)

    async def send(self, callback_url: str, payload: WebhookPayload) -> None:
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Secret": self.settings.ai_webhook_secret,
        }

        last_error: Exception | None = None
        for attempt in range(self.settings.webhook_max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.settings.webhook_timeout_seconds) as client:
                    response = await client.post(
                        callback_url,
                        json=payload.model_dump(exclude_none=True),
                        headers=headers,
                    )
                    response.raise_for_status()
                    logger.info(
                        "Delivered webhook publication_id=%s status=%s http_status=%s",
                        payload.publication_id,
                        payload.status,
                        response.status_code,
                    )
                    return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Webhook delivery failed publication_id=%s attempt=%s error=%s",
                    payload.publication_id,
                    attempt + 1,
                    exc,
                )
                if attempt < self.settings.webhook_max_retries:
                    await asyncio.sleep(self.settings.webhook_retry_backoff_seconds * (attempt + 1))

        if last_error is not None:
            logger.error(
                "Webhook delivery exhausted retries publication_id=%s error=%s",
                payload.publication_id,
                last_error,
            )
