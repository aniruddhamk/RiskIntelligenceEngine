"""
Unit tests for Rule Engine service.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

import pytest
from fastapi.testclient import TestClient
from services.rule_engine.app.main import app  # noqa
from services.rule_engine.app.engine.rule_evaluator import RuleEvaluator  # noqa


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def evaluator():
    return RuleEvaluator()


class TestRuleEvaluator:

    def test_sanctions_country_triggers(self, evaluator):
        data = {
            "client_id": "TEST001",
            "country": "KP",
            "industry": "trading",
            "pep_flag": False,
            "adverse_media": False,
            "transaction_volume": 100000,
            "cross_border_ratio": 0.2,
            "cash_ratio": 0.1,
            "client_type": "CORPORATE",
        }
        result = evaluator.evaluate(data)
        assert result["rule_score"] >= 50
        assert any("Sanctioned" in r for r in result["triggered_rules"])

    def test_pep_flag_triggers(self, evaluator):
        data = {
            "client_id": "TEST002",
            "country": "US",
            "industry": "banking",
            "pep_flag": True,
            "adverse_media": False,
            "transaction_volume": 50000,
            "cross_border_ratio": 0.1,
            "cash_ratio": 0.05,
            "client_type": "INDIVIDUAL",
        }
        result = evaluator.evaluate(data)
        assert result["rule_score"] >= 30
        assert any("PEP" in r for r in result["triggered_rules"])

    def test_clean_client_low_score(self, evaluator):
        data = {
            "client_id": "TEST003",
            "country": "DE",
            "industry": "manufacturing",
            "pep_flag": False,
            "adverse_media": False,
            "transaction_volume": 10000,
            "cross_border_ratio": 0.1,
            "cash_ratio": 0.05,
            "client_type": "CORPORATE",
        }
        result = evaluator.evaluate(data)
        assert result["rule_score"] < 30
        assert len(result["triggered_rules"]) == 0

    def test_crypto_high_risk(self, evaluator):
        data = {
            "client_id": "TEST004",
            "country": "US",
            "industry": "cryptocurrency exchange",
            "pep_flag": False,
            "adverse_media": False,
            "transaction_volume": 500000,
            "cross_border_ratio": 0.4,
            "cash_ratio": 0.05,
            "client_type": "CORPORATE",
        }
        result = evaluator.evaluate(data)
        assert result["rule_score"] >= 20

    def test_score_capped_at_100(self, evaluator):
        data = {
            "client_id": "TEST005",
            "country": "KP",
            "industry": "gambling",
            "pep_flag": True,
            "adverse_media": True,
            "transaction_volume": 50_000_000,
            "cross_border_ratio": 0.95,
            "cash_ratio": 0.80,
            "client_type": "CORPORATE",
        }
        result = evaluator.evaluate(data)
        assert result["rule_score"] <= 100.0

    def test_high_cash_ratio_triggers(self, evaluator):
        data = {
            "client_id": "TEST006",
            "country": "US",
            "industry": "retail",
            "pep_flag": False,
            "adverse_media": False,
            "transaction_volume": 200000,
            "cross_border_ratio": 0.05,
            "cash_ratio": 0.45,  # > 30%
            "client_type": "SME",
        }
        result = evaluator.evaluate(data)
        assert any("cash" in r.lower() for r in result["triggered_rules"])


class TestRuleEngineAPI:

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_evaluate_endpoint(self, client):
        payload = {
            "client_id": "CL12345",
            "country": "AE",
            "industry": "Trading",
            "pep_flag": False,
            "adverse_media": False,
            "transaction_volume": 15000000,
            "cross_border_ratio": 0.65,
            "cash_ratio": 0.08,
            "client_type": "CORPORATE",
        }
        resp = client.post("/api/v1/rules/evaluate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "rule_score" in data
        assert 0 <= data["rule_score"] <= 100
        assert "triggered_rules" in data

    def test_list_rules_endpoint(self, client):
        resp = client.get("/api/v1/rules/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "rules" in data
        assert data["count"] > 0
