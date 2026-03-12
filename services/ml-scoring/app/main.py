"""
ML Scoring Service – XGBoost + Random Forest ensemble for AML risk prediction.
"""
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, Optional

import numpy as np
import joblib
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.models.aml_model import AMLEnsembleModel

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s – %(message)s")
logger = logging.getLogger(__name__)

_model: Optional[AMLEnsembleModel] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model
    logger.info("🚀 ML Scoring Service starting up – loading model...")
    _model = AMLEnsembleModel()
    _model.load_or_train()
    logger.info(f"✅ Model loaded: {_model.version}")
    yield
    logger.info("🛑 ML Scoring Service shutting down...")


app = FastAPI(
    title="ML Scoring Service",
    description="XGBoost + Random Forest ensemble model for AML suspicious activity detection",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

router = APIRouter()


class FeatureInput(BaseModel):
    client_id: str
    transaction_volume: float = 0.0
    cross_border_ratio: float = 0.0
    cash_ratio: float = 0.0
    network_degree: int = 0
    pep_flag: float = 0.0
    country_risk_score: float = 0.0
    industry_risk_score: float = 0.0
    adverse_media_score: float = 0.0
    transaction_count: int = 0
    avg_transaction_size: float = 0.0
    distance_to_sanctioned: Optional[int] = None
    network_cluster_size: int = 0


class ScoringRequest(BaseModel):
    client_id: str
    features: FeatureInput


class ScoringResponse(BaseModel):
    client_id: str
    probability_suspicious: float = Field(..., ge=0, le=1)
    model_version: str
    feature_importances: Optional[Dict[str, float]] = None
    scored_at: datetime = Field(default_factory=datetime.utcnow)


@router.post("/ml/score", response_model=ScoringResponse)
async def score(request: ScoringRequest) -> ScoringResponse:
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not yet loaded")
    prob, importances = _model.predict(request.features.model_dump())
    return ScoringResponse(
        client_id=request.client_id,
        probability_suspicious=round(float(prob), 4),
        model_version=_model.version,
        feature_importances=importances,
    )


@router.get("/ml/model-info")
async def model_info():
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not yet loaded")
    return {"version": _model.version, "features": _model.feature_names, "model_types": ["xgboost", "random_forest"]}


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "ml-scoring", "model_loaded": _model is not None}


app.include_router(router, prefix="/api/v1", tags=["ML Scoring"])
