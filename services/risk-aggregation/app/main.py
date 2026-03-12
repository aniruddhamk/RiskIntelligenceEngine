"""
Risk Aggregation Service – combines rule, ML, and graph scores into composite risk.
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from common.utils.risk_data import compute_risk_rating

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s – %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Risk Aggregation Service starting up...")
    yield


app = FastAPI(
    title="Risk Aggregation Service",
    description="Weighted combination of rule-based, ML, and graph risk scores",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
router = APIRouter()


class AggregationRequest(BaseModel):
    client_id: str
    rule_score: float = Field(..., ge=0, le=100, description="Rule engine score (0-100)")
    ml_probability: float = Field(..., ge=0, le=1, description="ML model probability (0.0-1.0)")
    graph_risk_score: float = Field(..., ge=0, le=100, description="Graph risk score (0-100)")
    rule_weight: float = Field(0.5, description="Weight for rule score")
    ml_weight: float = Field(0.3, description="Weight for ML score")
    graph_weight: float = Field(0.2, description="Weight for graph score")


class AggregationResponse(BaseModel):
    client_id: str
    final_score: float = Field(..., ge=0, le=100)
    risk_rating: str
    rule_contribution: float
    ml_contribution: float
    graph_contribution: float
    formula: str
    aggregated_at: datetime = Field(default_factory=datetime.utcnow)


@router.post("/risk/aggregate", response_model=AggregationResponse)
async def aggregate_risk(request: AggregationRequest) -> AggregationResponse:
    """
    Weighted aggregation formula:
    final_score = (rule_score * rule_weight) + (ml_probability * 100 * ml_weight) + (graph_score * graph_weight)

    Default weights: rule=0.5, ml=0.3, graph=0.2
    """
    rule_contribution = request.rule_score * request.rule_weight
    ml_contribution = request.ml_probability * 100 * request.ml_weight
    graph_contribution = request.graph_risk_score * request.graph_weight

    final_score = round(min(rule_contribution + ml_contribution + graph_contribution, 100.0), 2)
    risk_rating = compute_risk_rating(final_score)

    formula = (
        f"({request.rule_score:.1f} × {request.rule_weight}) + "
        f"({request.ml_probability:.3f}×100 × {request.ml_weight}) + "
        f"({request.graph_risk_score:.1f} × {request.graph_weight}) "
        f"= {final_score:.2f}"
    )

    logger.info(f"Aggregated score for {request.client_id}: {final_score:.2f} ({risk_rating})")

    return AggregationResponse(
        client_id=request.client_id,
        final_score=final_score,
        risk_rating=risk_rating,
        rule_contribution=round(rule_contribution, 2),
        ml_contribution=round(ml_contribution, 2),
        graph_contribution=round(graph_contribution, 2),
        formula=formula,
    )


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "risk-aggregation"}


app.include_router(router, prefix="/api/v1", tags=["Risk Aggregation"])
