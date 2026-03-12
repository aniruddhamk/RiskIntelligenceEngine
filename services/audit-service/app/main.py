"""
Audit Service – immutable regulatory audit logging.
Subscribes to all Kafka topics and records every event for compliance.
"""
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, APIRouter, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s – %(message)s")
logger = logging.getLogger(__name__)

# In-memory audit log (replace with append-only PostgreSQL table in production)
_audit_logs: list = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Audit Service starting up...")
    yield


app = FastAPI(
    title="Audit Service",
    description="Immutable regulatory audit logging – records all system events for compliance",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
router = APIRouter()


class AuditLogEntry(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    client_id: Optional[str] = None
    actor: Optional[str] = None
    details: dict = Field(default_factory=dict)
    ip_address: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AuditLogResponse(BaseModel):
    event_id: str
    event_type: str
    client_id: Optional[str]
    actor: Optional[str]
    details: dict
    ip_address: Optional[str]
    timestamp: datetime


@router.post("/audit/log", response_model=AuditLogResponse, status_code=201)
async def create_audit_log(entry: AuditLogEntry) -> AuditLogResponse:
    """Record an audit event. This endpoint is append-only – records cannot be modified."""
    _audit_logs.append(entry)
    logger.info(f"Audit: [{entry.event_type}] client={entry.client_id} actor={entry.actor}")
    return AuditLogResponse(**entry.model_dump())


@router.get("/audit/logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    client_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
) -> List[AuditLogResponse]:
    """Query audit logs with optional filters."""
    logs = _audit_logs
    if client_id:
        logs = [l for l in logs if l.client_id == client_id]
    if event_type:
        logs = [l for l in logs if l.event_type == event_type]
    sorted_logs = sorted(logs, key=lambda l: l.timestamp, reverse=True)
    return [AuditLogResponse(**l.model_dump()) for l in sorted_logs[offset:offset + limit]]


@router.get("/audit/logs/{event_id}", response_model=AuditLogResponse)
async def get_audit_log(event_id: str) -> AuditLogResponse:
    for log in _audit_logs:
        if log.event_id == event_id:
            return AuditLogResponse(**log.model_dump())
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail=f"Audit log {event_id} not found")


@router.get("/audit/stats")
async def audit_stats() -> dict:
    total = len(_audit_logs)
    by_type = {}
    for log in _audit_logs:
        by_type[log.event_type] = by_type.get(log.event_type, 0) + 1
    return {"total_events": total, "by_event_type": by_type}


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "audit-service", "total_logs": len(_audit_logs)}


app.include_router(router, prefix="/api/v1", tags=["Audit Logging"])
