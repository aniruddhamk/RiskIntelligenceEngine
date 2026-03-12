"""
Pydantic schemas shared across all AML microservices.
"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ─── Enums ───────────────────────────────────────────────────────────────────

class RiskRating(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ClientType(str, Enum):
    INDIVIDUAL = "INDIVIDUAL"
    CORPORATE = "CORPORATE"
    SME = "SME"


class AlertType(str, Enum):
    SUSPICIOUS_ACTIVITY = "SuspiciousActivity"
    STRUCTURING = "Structuring"
    ROUND_TRIPPING = "RoundTripping"
    SANCTIONS_MATCH = "SanctionsMatch"
    HIGH_RISK_NETWORK = "HighRiskNetwork"


class AlertStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    CLOSED = "CLOSED"
    ESCALATED = "ESCALATED"


# ─── Transaction Models ───────────────────────────────────────────────────────

class TransactionData(BaseModel):
    monthly_volume: float = Field(..., ge=0, description="Monthly transaction volume in USD")
    international_ratio: float = Field(..., ge=0, le=1, description="Ratio of cross-border transactions")
    cash_ratio: float = Field(..., ge=0, le=1, description="Ratio of cash transactions")
    transaction_count: Optional[int] = Field(None, description="Number of transactions per month")
    avg_transaction_size: Optional[float] = Field(None, description="Average transaction size in USD")


class TransactionEvent(BaseModel):
    event_type: str = Field("transaction_event")
    client_id: str = Field(..., description="Unique client identifier")
    transaction_id: str = Field(..., description="Unique transaction identifier")
    amount: float = Field(..., ge=0, description="Transaction amount in USD")
    currency: str = Field(..., max_length=3, description="ISO 4217 currency code")
    destination_country: str = Field(..., max_length=2, description="ISO 3166-1 alpha-2 country code")
    origin_country: str = Field(..., max_length=2, description="ISO 3166-1 alpha-2 country code")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_international: bool = Field(False)
    is_cash: bool = Field(False)
    counterparty_id: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


# ─── Client Risk Request ──────────────────────────────────────────────────────

class ClientRiskRequest(BaseModel):
    client_id: str = Field(..., description="Unique client identifier")
    client_type: ClientType = Field(..., description="Client type")
    country: str = Field(..., max_length=2, description="ISO 3166-1 alpha-2 country code")
    industry: str = Field(..., description="Client's primary industry")
    pep_flag: bool = Field(False, description="Politically Exposed Person indicator")
    adverse_media: bool = Field(False, description="Adverse media flag")
    years_in_business: Optional[int] = Field(None, ge=0)
    transactions: TransactionData
    source_of_funds: Optional[str] = None


class TransactionRiskRequest(BaseModel):
    transaction_id: str = Field(..., description="Unique transaction identifier")
    client_id: str = Field(..., description="Client performing the transaction")
    amount: float = Field(..., ge=0)
    currency: str = Field(..., max_length=3)
    destination_country: str = Field(..., max_length=2)
    is_international: bool = False
    is_cash: bool = False
    transaction_type: str = Field("WIRE", description="WIRE/CASH/SWIFT/INTERNAL")


# ─── Feature Vector ───────────────────────────────────────────────────────────

class FeatureVector(BaseModel):
    client_id: str
    transaction_volume: float
    cross_border_ratio: float
    cash_ratio: float
    network_degree: int = Field(0, description="Number of graph connections")
    pep_flag: float = Field(0.0, description="1.0 if PEP, 0.0 otherwise")
    country_risk_score: float = Field(0.0, ge=0, le=100)
    industry_risk_score: float = Field(0.0, ge=0, le=100)
    adverse_media_score: float = Field(0.0, ge=0, le=100)
    transaction_count: int = 0
    avg_transaction_size: float = 0.0
    distance_to_sanctioned: Optional[int] = Field(None, description="Graph hops to nearest sanctioned entity")
    network_cluster_size: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─── Rule Evaluation ─────────────────────────────────────────────────────────

class RuleEvaluationRequest(BaseModel):
    client_id: str
    country: str
    industry: str
    pep_flag: bool
    adverse_media: bool
    transaction_volume: float
    cross_border_ratio: float
    cash_ratio: float
    client_type: ClientType
    source_of_funds: Optional[str] = None


class RuleEvaluationResult(BaseModel):
    client_id: str
    rule_score: float = Field(..., ge=0, le=100)
    triggered_rules: List[str] = Field(default_factory=list)
    rule_details: Dict[str, Any] = Field(default_factory=dict)


# ─── ML Scoring ──────────────────────────────────────────────────────────────

class MLScoringRequest(BaseModel):
    client_id: str
    features: FeatureVector


class MLScoringResult(BaseModel):
    client_id: str
    probability_suspicious: float = Field(..., ge=0, le=1)
    model_version: str
    feature_importances: Optional[Dict[str, float]] = None


# ─── Graph Risk ──────────────────────────────────────────────────────────────

class GraphRiskRequest(BaseModel):
    client_id: str
    include_network_analysis: bool = True


class GraphRiskResult(BaseModel):
    client_id: str
    graph_risk_score: float = Field(..., ge=0, le=100)
    degree_centrality: float = 0.0
    page_rank: float = 0.0
    distance_to_sanctioned: Optional[int] = None
    network_cluster_size: int = 0
    top_risky_connections: List[str] = Field(default_factory=list)


# ─── Aggregation ─────────────────────────────────────────────────────────────

class AggregationRequest(BaseModel):
    client_id: str
    rule_score: float
    ml_probability: float
    graph_risk_score: float
    rule_weight: float = 0.5
    ml_weight: float = 0.3
    graph_weight: float = 0.2


class RiskScoreResponse(BaseModel):
    client_id: str
    risk_score: float = Field(..., ge=0, le=100)
    risk_rating: RiskRating
    rule_score: float
    ml_probability: float
    graph_risk_score: float
    top_risk_drivers: List[str] = Field(default_factory=list)
    model_version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─── Alert ───────────────────────────────────────────────────────────────────

class AlertCreateRequest(BaseModel):
    alert_type: AlertType
    client_id: str
    risk_score: float = Field(..., ge=0, le=100)
    reason: str
    transaction_id: Optional[str] = None
    assigned_to: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AlertResponse(BaseModel):
    alert_id: str
    alert_type: AlertType
    client_id: str
    risk_score: float
    risk_rating: RiskRating
    reason: str
    status: AlertStatus = AlertStatus.OPEN
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


# ─── Audit ───────────────────────────────────────────────────────────────────

class AuditLog(BaseModel):
    event_id: str
    event_type: str
    client_id: Optional[str] = None
    actor: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None


# ─── Health Check ────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
