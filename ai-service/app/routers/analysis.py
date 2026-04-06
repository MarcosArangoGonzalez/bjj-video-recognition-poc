from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from app.schemas.analysis import AnalysisAcceptedResponse, AnalysisRequest
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix="/api/v1", tags=["analysis"])


def get_analysis_service(request: Request) -> AnalysisService:
    return request.app.state.analysis_service


@router.post(
    "/analyze-video",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AnalysisAcceptedResponse,
)
async def analyze_video(
    payload: AnalysisRequest,
    background_tasks: BackgroundTasks,
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisAcceptedResponse:
    accepted = analysis_service.accept_analysis(payload)
    background_tasks.add_task(analysis_service.process_analysis_task, accepted.publication_id, payload)
    return accepted
