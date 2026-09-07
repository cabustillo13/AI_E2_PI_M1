from fastapi import APIRouter, HTTPException

from src.models.request import TriageRequest
from src.models.response import TriageResponse
from src.pipeline.triage import TriagePipeline


router = APIRouter()
pipeline = TriagePipeline()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/triage", response_model=TriageResponse)
def triage(request: TriageRequest) -> TriageResponse:
    try:
        return pipeline.run(request.query)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from exc