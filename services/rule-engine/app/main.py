"""
Rule Engine Service – evaluates configurable AML rules against client data.
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, APIRouter, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s – %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Rule Engine Service starting up...")
    yield
    logger.info("🛑 Rule Engine Service shutting down...")


app = FastAPI(
    title="Rule Engine Service",
    description="Configurable AML rule evaluation engine – evaluates clients against risk rules",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ─── Router ──────────────────────────────────────────────────────────────────
from app.engine.rule_evaluator import RuleEvaluator
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

router = APIRouter()
_evaluator = RuleEvaluator()


class RuleRequest(BaseModel):
    client_id: str
    country: str
    industry: str
    pep_flag: bool
    adverse_media: bool
    transaction_volume: float
    cross_border_ratio: float
    cash_ratio: float
    client_type: str
    source_of_funds: Optional[str] = None


class RuleResult(BaseModel):
    client_id: str
    rule_score: float
    triggered_rules: List[str]
    rule_details: Dict[str, Any]
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


@router.post("/rules/evaluate", response_model=RuleResult)
async def evaluate_rules(request: RuleRequest) -> RuleResult:
    result = _evaluator.evaluate(request.model_dump())
    return RuleResult(**result)


@router.get("/rules/list", summary="List all configured rules")
async def list_rules():
    return {"rules": _evaluator.get_rules(), "count": len(_evaluator.get_rules())}


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "rule-engine", "timestamp": datetime.utcnow().isoformat()}


app.include_router(router, prefix="/api/v1", tags=["Rule Engine"])
