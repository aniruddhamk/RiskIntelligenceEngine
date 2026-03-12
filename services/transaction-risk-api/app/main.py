"""
Transaction Risk API – real-time transaction monitoring and risk scoring.
"""
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from common.utils.risk_data import (
    get_country_risk, compute_risk_rating, is_sanctioned_country
)

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s – %(message)s")
logger = logging.getLogger(__name__)

# Structuring detection: track per-client transaction accumulator
_tx_accumulator: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Transaction Risk API starting up...")
    yield


app = FastAPI(
    title="Transaction Risk API",
    description="Real-time AML risk monitoring for individual transactions",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
router = APIRouter()

# Structuring threshold (just below CTR $10,000 reporting threshold)
STRUCTURING_THRESHOLD = 9_000
CTR_THRESHOLD = 10_000
LARGE_TX_THRESHOLD = 1_000_000


class TransactionRiskRequest(BaseModel):
    transaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str
    amount: float = Field(..., ge=0)
    currency: str = Field("USD", max_length=3)
    destination_country: str = Field(..., max_length=2)
    origin_country: str = Field("US", max_length=2)
    is_international: bool = False
    is_cash: bool = False
    transaction_type: str = Field("WIRE", description="WIRE / CASH / SWIFT / INTERNAL / CRYPTO")
    counterparty_id: Optional[str] = None


class TransactionRiskResponse(BaseModel):
    transaction_id: str
    client_id: str
    risk_score: float
    risk_rating: str
    flags: list
    structuring_suspected: bool
    ctr_required: bool
    recommendation: str
    checked_at: datetime = Field(default_factory=datetime.utcnow)


class TransactionRiskEngine:
    """Evaluates a transaction for AML red flags."""

    def evaluate(self, request: TransactionRiskRequest) -> dict:
        score = 0.0
        flags = []
        structuring = False

        # Country risk
        dest_risk = get_country_risk(request.destination_country)
        if dest_risk > 70:
            score += 30
            flags.append(f"High-risk destination country: {request.destination_country}")
        elif dest_risk > 50:
            score += 15
            flags.append(f"Medium-risk destination country: {request.destination_country}")

        # Sanctions check
        if is_sanctioned_country(request.destination_country):
            score += 50
            flags.append(f"SANCTIONED destination country: {request.destination_country}")

        # Cash transaction
        if request.is_cash:
            score += 15
            flags.append("Cash transaction")

        # Large transaction
        if request.amount >= LARGE_TX_THRESHOLD:
            score += 20
            flags.append(f"Large transaction: ${request.amount:,.0f}")

        # CTR threshold proximity (structuring detection)
        if STRUCTURING_THRESHOLD <= request.amount < CTR_THRESHOLD:
            score += 25
            flags.append("Amount just below CTR reporting threshold (structuring suspected)")
            structuring = True

        # Crypto exposure
        if request.transaction_type.upper() == "CRYPTO":
            score += 15
            flags.append("Cryptocurrency transaction")

        # Round number detection (often indicative of money laundering)
        if request.amount > 1000 and request.amount % 1000 == 0:
            score += 5
            flags.append("Round-number transaction amount")

        # Accumulate for multi-transaction structuring detection
        client_accum = _tx_accumulator.get(request.client_id, 0) + request.amount
        _tx_accumulator[request.client_id] = client_accum
        if client_accum > CTR_THRESHOLD and request.amount < CTR_THRESHOLD:
            score += 20
            flags.append(f"Cumulative amount ${client_accum:,.0f} exceeds CTR threshold across transactions")
            structuring = True

        final_score = min(score, 100.0)
        risk_rating = compute_risk_rating(final_score)

        recommendation = "ALLOW"
        if risk_rating == "CRITICAL":
            recommendation = "BLOCK_AND_REPORT"
        elif risk_rating == "HIGH":
            recommendation = "MANUAL_REVIEW"
        elif risk_rating == "MEDIUM":
            recommendation = "ENHANCED_MONITORING"

        return {
            "transaction_id": request.transaction_id,
            "client_id": request.client_id,
            "risk_score": round(final_score, 2),
            "risk_rating": risk_rating,
            "flags": flags,
            "structuring_suspected": structuring,
            "ctr_required": request.amount >= CTR_THRESHOLD or request.is_cash and request.amount >= CTR_THRESHOLD,
            "recommendation": recommendation,
        }


_engine = TransactionRiskEngine()


@router.post("/transaction-risk/check", response_model=TransactionRiskResponse)
async def check_transaction_risk(request: TransactionRiskRequest) -> TransactionRiskResponse:
    """
    Real-time AML risk check for a financial transaction.
    Checks for structuring, sanctions exposure, high-risk country, and large transactions.
    """
    result = _engine.evaluate(request)
    logger.info(
        f"Transaction {request.transaction_id} [{request.client_id}]: "
        f"${request.amount:,.0f} → {request.destination_country} | "
        f"score={result['risk_score']} ({result['risk_rating']})"
    )
    return TransactionRiskResponse(**result)


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "transaction-risk-api"}


app.include_router(router, prefix="/api/v1", tags=["Transaction Risk"])
