"""Health check router – shared across all services."""
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: str


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Liveness probe endpoint."""
    return HealthResponse(
        status="healthy",
        service="client-risk-api",
        timestamp=datetime.utcnow().isoformat(),
    )
