"""
Alert Service – creates, manages and queries AML alerts.
"""
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, APIRouter, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from common.utils.risk_data import compute_risk_rating

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s – %(message)s")
logger = logging.getLogger(__name__)

# In-memory store (replace with PostgreSQL in production)
_alerts: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Alert Service starting up...")
    yield


app = FastAPI(
    title="Alert Service",
    description="AML alert generation, management, and querying",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
router = APIRouter()


class AlertCreateRequest(BaseModel):
    alert_type: str = Field(..., description="SuspiciousActivity | Structuring | SanctionsMatch | HighRiskNetwork")
    client_id: str
    risk_score: float = Field(..., ge=0, le=100)
    reason: str
    transaction_id: Optional[str] = None
    assigned_to: Optional[str] = None
    metadata: Optional[dict] = None


class AlertResponse(BaseModel):
    alert_id: str
    alert_type: str
    client_id: str
    risk_score: float
    risk_rating: str
    reason: str
    status: str = "OPEN"
    transaction_id: Optional[str] = None
    assigned_to: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class AlertUpdateRequest(BaseModel):
    status: str = Field(..., description="OPEN | UNDER_REVIEW | CLOSED | ESCALATED")
    assigned_to: Optional[str] = None
    notes: Optional[str] = None


@router.post("/alerts/create", response_model=AlertResponse, status_code=201)
async def create_alert(request: AlertCreateRequest) -> AlertResponse:
    """Create a new AML alert."""
    alert_id = str(uuid.uuid4())
    risk_rating = compute_risk_rating(request.risk_score)

    alert = AlertResponse(
        alert_id=alert_id,
        alert_type=request.alert_type,
        client_id=request.client_id,
        risk_score=request.risk_score,
        risk_rating=risk_rating,
        reason=request.reason,
        transaction_id=request.transaction_id,
        assigned_to=request.assigned_to,
        metadata=request.metadata,
    )
    _alerts[alert_id] = alert
    logger.info(f"Alert created: {alert_id} for client {request.client_id} – {risk_rating}")
    return alert


@router.get("/alerts/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: str) -> AlertResponse:
    if alert_id not in _alerts:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return _alerts[alert_id]


@router.get("/alerts/client/{client_id}", response_model=List[AlertResponse])
async def get_client_alerts(
    client_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, le=200),
) -> List[AlertResponse]:
    """Get all alerts for a client, optionally filtered by status."""
    alerts = [a for a in _alerts.values() if a.client_id == client_id]
    if status:
        alerts = [a for a in alerts if a.status == status.upper()]
    return sorted(alerts, key=lambda a: a.created_at, reverse=True)[:limit]


@router.patch("/alerts/{alert_id}", response_model=AlertResponse)
async def update_alert(alert_id: str, update: AlertUpdateRequest) -> AlertResponse:
    if alert_id not in _alerts:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    alert = _alerts[alert_id]
    alert.status = update.status.upper()
    if update.assigned_to:
        alert.assigned_to = update.assigned_to
    alert.updated_at = datetime.utcnow()
    return alert


@router.get("/alerts", response_model=List[AlertResponse])
async def list_alerts(
    status: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
) -> List[AlertResponse]:
    alerts = list(_alerts.values())
    if status:
        alerts = [a for a in alerts if a.status == status.upper()]
    if alert_type:
        alerts = [a for a in alerts if a.alert_type == alert_type]
    return sorted(alerts, key=lambda a: a.risk_score, reverse=True)[:limit]


@router.get("/alerts/stats/summary")
async def alert_stats() -> dict:
    total = len(_alerts)
    by_status = {}
    by_rating = {}
    for a in _alerts.values():
        by_status[a.status] = by_status.get(a.status, 0) + 1
        by_rating[a.risk_rating] = by_rating.get(a.risk_rating, 0) + 1
    return {"total": total, "by_status": by_status, "by_rating": by_rating}


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "alert-service", "active_alerts": len(_alerts)}


app.include_router(router, prefix="/api/v1", tags=["Alert Management"])
