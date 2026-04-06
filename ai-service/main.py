from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.routers.analysis import router as analysis_router
from app.services.analysis_service import AnalysisService

load_dotenv()
configure_logging()
logger = get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting ai-service")
        app.state.settings = settings
        app.state.analysis_service = AnalysisService(settings)
        yield
        app.state.analysis_service.pipeline.sidecar.close()
        logger.info("Stopping ai-service")

    app = FastAPI(
        title="BJJ AI Service",
        description="Contract-first AI service for asynchronous BJJ video analysis.",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(analysis_router)

    @app.get("/health", tags=["ops"])
    async def health() -> dict:
        analysis_service: AnalysisService = app.state.analysis_service
        return analysis_service.health_payload()

    return app


app = create_app()
