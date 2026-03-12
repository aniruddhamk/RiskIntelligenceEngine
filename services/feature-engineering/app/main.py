"""
Feature Engineering Service – computes ML feature vectors from raw client data.
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import redis.asyncio as aioredis
from fastapi import FastAPI, APIRouter, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from common.utils.risk_data import get_country_risk, get_industry_risk

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s – %(message)s")
logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis
    try:
        import os
        _redis = await aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.warning(f"Redis not available: {e}")
    yield
    if _redis:
        await _redis.close()


app = FastAPI(
    title="Feature Engineering Service",
    description="Computes AML feature vectors from raw client/transaction data, with Redis caching",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
router = APIRouter()


class FeatureRequest(BaseModel):
    client_id: str
    country: str
    industry: str
    pep_flag: bool = False
    adverse_media: bool = False
    monthly_volume: float = Field(..., ge=0)
    international_ratio: float = Field(..., ge=0, le=1)
    cash_ratio: float = Field(..., ge=0, le=1)
    transaction_count: int = 0
    avg_transaction_size: float = 0.0
    network_degree: int = 0
    network_cluster_size: int = 0
    distance_to_sanctioned: Optional[int] = None


class FeatureResponse(BaseModel):
    client_id: str
    transaction_volume: float
    cross_border_ratio: float
    cash_ratio: float
    network_degree: int
    pep_flag: float
    country_risk_score: float
    industry_risk_score: float
    adverse_media_score: float
    transaction_count: int
    avg_transaction_size: float
    distance_to_sanctioned: Optional[int]
    network_cluster_size: int
    computed_at: datetime = Field(default_factory=datetime.utcnow)


async def _cache_get(key: str) -> Optional[str]:
    if _redis:
        try:
            return await _redis.get(key)
        except Exception:
            pass
    return None


async def _cache_set(key: str, value: str, ttl: int = 300) -> None:
    if _redis:
        try:
            await _redis.setex(key, ttl, value)
        except Exception:
            pass


@router.post("/features/generate", response_model=FeatureResponse)
async def generate_features(request: FeatureRequest) -> FeatureResponse:
    """
    Generate a normalized feature vector for ML scoring.
    Results are cached in Redis for 5 minutes per client.
    """
    cache_key = f"features:{request.client_id}"

    # Try cache
    cached = await _cache_get(cache_key)
    if cached:
        import json
        data = json.loads(cached)
        data["computed_at"] = datetime.utcnow()
        return FeatureResponse(**data)

    # Compute features
    country_risk = get_country_risk(request.country)
    industry_risk = get_industry_risk(request.industry)
    adverse_media_score = 60.0 if request.adverse_media else 0.0

    avg_tx = request.avg_transaction_size
    if avg_tx == 0 and request.transaction_count > 0:
        avg_tx = request.monthly_volume / request.transaction_count

    response = FeatureResponse(
        client_id=request.client_id,
        transaction_volume=request.monthly_volume,
        cross_border_ratio=request.international_ratio,
        cash_ratio=request.cash_ratio,
        network_degree=request.network_degree,
        pep_flag=1.0 if request.pep_flag else 0.0,
        country_risk_score=country_risk,
        industry_risk_score=industry_risk,
        adverse_media_score=adverse_media_score,
        transaction_count=request.transaction_count,
        avg_transaction_size=avg_tx,
        distance_to_sanctioned=request.distance_to_sanctioned,
        network_cluster_size=request.network_cluster_size,
    )

    # Cache result
    import json
    data = response.model_dump()
    data["computed_at"] = data["computed_at"].isoformat()
    await _cache_set(cache_key, json.dumps(data))

    logger.info(f"Features computed for {request.client_id}: country_risk={country_risk}, industry_risk={industry_risk}")
    return response


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "feature-engineering"}


app.include_router(router, prefix="/api/v1", tags=["Feature Engineering"])
