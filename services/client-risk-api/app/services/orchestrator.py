"""
Risk Scoring orchestrator – coordinates feature, rule, ML, graph, and aggregation services.
"""
import logging
import httpx
from datetime import datetime
from typing import Dict, Any, List

from common.config import get_settings
from common.models.schemas import (
    ClientRiskRequest, RiskScoreResponse, RiskRating,
    FeatureVector, RuleEvaluationRequest, MLScoringRequest,
    GraphRiskRequest, AggregationRequest, AlertCreateRequest, AlertType,
)
from common.utils.risk_data import compute_risk_rating, get_country_risk, get_industry_risk
from common.kafka.client import AMLProducer, TOPICS

logger = logging.getLogger(__name__)


class RiskOrchestrator:
    """
    Orchestrates the full AML risk scoring pipeline:
    1. Feature Engineering → 2. Rule Engine → 3. ML Scoring → 4. Graph Intelligence → 5. Risk Aggregation
    """

    def __init__(self):
        self.settings = get_settings()
        self._producer = None

    def _get_producer(self) -> AMLProducer:
        if self._producer is None:
            self._producer = AMLProducer(self.settings.kafka_bootstrap_servers)
        return self._producer

    async def score_client(self, request: ClientRiskRequest) -> RiskScoreResponse:
        """Execute the full scoring pipeline for a client."""
        client_id = request.client_id
        logger.info(f"Starting risk scoring pipeline for client {client_id}")

        async with httpx.AsyncClient(timeout=30.0) as http:
            # Step 1: Generate Features
            features = await self._generate_features(http, request)
            logger.info(f"Features generated for {client_id}: cross_border={features.cross_border_ratio:.2f}")

            # Step 2: Rule Engine Evaluation
            rule_result = await self._evaluate_rules(http, request)
            logger.info(f"Rule score for {client_id}: {rule_result['rule_score']:.1f}")

            # Step 3: ML Scoring
            ml_result = await self._ml_score(http, client_id, features)
            logger.info(f"ML probability for {client_id}: {ml_result['probability_suspicious']:.3f}")

            # Step 4: Graph Risk Analysis
            graph_result = await self._graph_risk(http, client_id)
            logger.info(f"Graph risk for {client_id}: {graph_result['graph_risk_score']:.1f}")

            # Step 5: Aggregate Scores
            aggregation_payload = {
                "client_id": client_id,
                "rule_score": rule_result["rule_score"],
                "ml_probability": ml_result["probability_suspicious"],
                "graph_risk_score": graph_result["graph_risk_score"],
            }
            final_result = await self._aggregate(http, aggregation_payload)
            risk_score = final_result["final_score"]
            risk_rating = compute_risk_rating(risk_score)

        # Build top risk drivers
        top_drivers = self._compute_risk_drivers(
            request, rule_result, ml_result, graph_result, features
        )

        response = RiskScoreResponse(
            client_id=client_id,
            risk_score=round(risk_score, 2),
            risk_rating=RiskRating(risk_rating),
            rule_score=rule_result["rule_score"],
            ml_probability=ml_result["probability_suspicious"],
            graph_risk_score=graph_result["graph_risk_score"],
            top_risk_drivers=top_drivers,
            model_version=self.settings.model_version,
            timestamp=datetime.utcnow(),
        )

        # Publish scoring event
        self._publish_score_event(response)

        # Trigger alert if high/critical
        if risk_rating in ("HIGH", "CRITICAL"):
            await self._create_alert(client_id, risk_score, risk_rating, top_drivers)

        return response

    async def _generate_features(self, http: httpx.AsyncClient, request: ClientRiskRequest) -> FeatureVector:
        payload = {
            "client_id": request.client_id,
            "country": request.country,
            "industry": request.industry,
            "pep_flag": request.pep_flag,
            "adverse_media": request.adverse_media,
            "monthly_volume": request.transactions.monthly_volume,
            "international_ratio": request.transactions.international_ratio,
            "cash_ratio": request.transactions.cash_ratio,
            "transaction_count": request.transactions.transaction_count or 0,
        }
        try:
            resp = await http.post(f"{self.settings.feature_service_url}/api/v1/features/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return FeatureVector(**data)
        except Exception as e:
            logger.warning(f"Feature service unavailable ({e}), using fallback computation")
            return self._fallback_features(request)

    def _fallback_features(self, request: ClientRiskRequest) -> FeatureVector:
        return FeatureVector(
            client_id=request.client_id,
            transaction_volume=request.transactions.monthly_volume,
            cross_border_ratio=request.transactions.international_ratio,
            cash_ratio=request.transactions.cash_ratio,
            pep_flag=1.0 if request.pep_flag else 0.0,
            country_risk_score=get_country_risk(request.country),
            industry_risk_score=get_industry_risk(request.industry),
            adverse_media_score=50.0 if request.adverse_media else 0.0,
            transaction_count=request.transactions.transaction_count or 0,
        )

    async def _evaluate_rules(self, http: httpx.AsyncClient, request: ClientRiskRequest) -> Dict[str, Any]:
        payload = {
            "client_id": request.client_id,
            "country": request.country,
            "industry": request.industry,
            "pep_flag": request.pep_flag,
            "adverse_media": request.adverse_media,
            "transaction_volume": request.transactions.monthly_volume,
            "cross_border_ratio": request.transactions.international_ratio,
            "cash_ratio": request.transactions.cash_ratio,
            "client_type": request.client_type,
        }
        try:
            resp = await http.post(f"{self.settings.rule_service_url}/api/v1/rules/evaluate", json=payload)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Rule service unavailable ({e}), using fallback rule evaluation")
            return self._fallback_rule_score(request)

    def _fallback_rule_score(self, request: ClientRiskRequest) -> Dict[str, Any]:
        score = 0.0
        triggered = []
        from common.utils.risk_data import is_sanctioned_country, HIGH_RISK_INDUSTRIES, PEP_RISK_BOOST
        if is_sanctioned_country(request.country):
            score += 50
            triggered.append("Sanctioned country")
        if request.pep_flag:
            score += PEP_RISK_BOOST
            triggered.append("PEP flag")
        if any(h in request.industry.lower() for h in HIGH_RISK_INDUSTRIES):
            score += 20
            triggered.append("High-risk industry")
        if request.transactions.international_ratio > 0.5:
            score += 10
            triggered.append("High international transaction ratio")
        return {"rule_score": min(score, 100), "triggered_rules": triggered, "rule_details": {}}

    async def _ml_score(self, http: httpx.AsyncClient, client_id: str, features: FeatureVector) -> Dict[str, Any]:
        payload = {"client_id": client_id, "features": features.model_dump()}
        try:
            resp = await http.post(f"{self.settings.ml_service_url}/api/v1/ml/score", json=payload)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"ML service unavailable ({e}), using heuristic probability")
            score = (
                features.cross_border_ratio * 0.3 +
                features.cash_ratio * 0.2 +
                (features.country_risk_score / 100) * 0.3 +
                features.pep_flag * 0.2
            )
            return {"probability_suspicious": min(score, 1.0), "model_version": "FALLBACK_HEURISTIC"}

    async def _graph_risk(self, http: httpx.AsyncClient, client_id: str) -> Dict[str, Any]:
        payload = {"client_id": client_id, "include_network_analysis": True}
        try:
            resp = await http.post(f"{self.settings.graph_service_url}/api/v1/graph/risk", json=payload)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Graph service unavailable ({e}), returning neutral graph score")
            return {"graph_risk_score": 30.0, "degree_centrality": 0.0, "page_rank": 0.0}

    async def _aggregate(self, http: httpx.AsyncClient, payload: Dict) -> Dict[str, Any]:
        try:
            resp = await http.post(f"{self.settings.aggregation_service_url}/api/v1/risk/aggregate", json=payload)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Aggregation service unavailable ({e}), computing locally")
            rule = payload["rule_score"]
            ml = payload["ml_probability"]
            graph = payload["graph_risk_score"]
            final = (rule * 0.5) + (ml * 100 * 0.3) + (graph * 0.2)
            return {"final_score": round(min(final, 100), 2)}

    async def _create_alert(self, client_id: str, risk_score: float, risk_rating: str, drivers: List[str]):
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                payload = {
                    "alert_type": "SuspiciousActivity",
                    "client_id": client_id,
                    "risk_score": risk_score,
                    "reason": f"Risk rating {risk_rating}: {'; '.join(drivers[:3])}",
                }
                await http.post(f"{self.settings.alert_service_url}/api/v1/alerts/create", json=payload)
        except Exception as e:
            logger.warning(f"Could not create alert: {e}")

    def _publish_score_event(self, response: RiskScoreResponse):
        try:
            producer = self._get_producer()
            producer.produce(
                topic=TOPICS["RISK_SCORE_GENERATED"],
                key=response.client_id,
                value=response.model_dump(mode="json"),
            )
            if response.risk_rating in (RiskRating.HIGH, RiskRating.CRITICAL):
                producer.produce(
                    topic=TOPICS["SUSPICIOUS_ACTIVITY"],
                    key=response.client_id,
                    value={
                        "client_id": response.client_id,
                        "risk_score": response.risk_score,
                        "risk_rating": response.risk_rating.value,
                        "top_risk_drivers": response.top_risk_drivers,
                    },
                )
        except Exception as e:
            logger.warning(f"Failed to publish Kafka event: {e}")

    def _compute_risk_drivers(
        self, request, rule_result, ml_result, graph_result, features: FeatureVector
    ) -> List[str]:
        drivers = []
        triggered_rules = rule_result.get("triggered_rules", [])
        drivers.extend(triggered_rules)

        if features.cross_border_ratio > 0.5:
            drivers.append("High cross-border transaction ratio")
        if features.cash_ratio > 0.3:
            drivers.append("High cash transaction ratio")
        prob = ml_result.get("probability_suspicious", 0)
        if prob > 0.7:
            drivers.append("ML model flags high suspicion probability")
        graph_score = graph_result.get("graph_risk_score", 0)
        if graph_score > 60:
            drivers.append("Network connection to high-risk entities")
        if request.transactions.monthly_volume > 10_000_000:
            drivers.append("Unusually high monthly transaction volume")
        return list(dict.fromkeys(drivers))[:5]
