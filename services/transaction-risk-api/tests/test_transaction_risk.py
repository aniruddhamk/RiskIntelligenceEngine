"""
Unit tests for Transaction Risk API.
"""
import pytest
from fastapi.testclient import TestClient

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))


@pytest.fixture
def client():
    from services.transaction_risk_api.app.main import app
    with TestClient(app) as c:
        yield c


class TestTransactionRiskAPI:

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_normal_transaction_low_risk(self, client):
        payload = {
            "transaction_id": "TX001",
            "client_id": "CL001",
            "amount": 5000,
            "currency": "USD",
            "destination_country": "US",
            "is_international": False,
            "is_cash": False,
            "transaction_type": "WIRE",
        }
        resp = client.post("/api/v1/transaction-risk/check", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_score"] < 40
        assert data["recommendation"] in ("ALLOW", "ENHANCED_MONITORING")

    def test_sanctioned_country_blocked(self, client):
        payload = {
            "transaction_id": "TX002",
            "client_id": "CL002",
            "amount": 10000,
            "currency": "USD",
            "destination_country": "KP",
            "is_international": True,
            "is_cash": False,
            "transaction_type": "SWIFT",
        }
        resp = client.post("/api/v1/transaction-risk/check", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_score"] >= 70
        assert "SANCTIONED" in " ".join(data["flags"]).upper()
        assert data["recommendation"] in ("BLOCK_AND_REPORT", "MANUAL_REVIEW")

    def test_structuring_detected(self, client):
        payload = {
            "transaction_id": "TX003",
            "client_id": "CL003",
            "amount": 9500,  # Just below CTR threshold
            "currency": "USD",
            "destination_country": "US",
            "is_international": False,
            "is_cash": True,
            "transaction_type": "CASH",
        }
        resp = client.post("/api/v1/transaction-risk/check", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["structuring_suspected"] is True

    def test_large_transaction_flagged(self, client):
        payload = {
            "transaction_id": "TX004",
            "client_id": "CL004",
            "amount": 5_000_000,
            "currency": "USD",
            "destination_country": "DE",
            "is_international": True,
            "is_cash": False,
            "transaction_type": "WIRE",
        }
        resp = client.post("/api/v1/transaction-risk/check", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_score"] > 20


class TestAlertService:

    def test_create_and_get_alert(self):
        from services.alert_service.app.main import app
        with TestClient(app) as c:
            payload = {
                "alert_type": "SuspiciousActivity",
                "client_id": "CL12345",
                "risk_score": 82,
                "reason": "High-risk network cluster",
            }
            resp = c.post("/api/v1/alerts/create", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["alert_id"]
            assert data["risk_rating"] == "CRITICAL"
            assert data["status"] == "OPEN"

            alert_id = data["alert_id"]
            resp2 = c.get(f"/api/v1/alerts/{alert_id}")
            assert resp2.status_code == 200
            assert resp2.json()["alert_id"] == alert_id

    def test_alert_stats(self):
        from services.alert_service.app.main import app
        with TestClient(app) as c:
            resp = c.get("/api/v1/alerts/stats/summary")
            assert resp.status_code == 200
            assert "total" in resp.json()


class TestRiskAggregation:

    def test_aggregate_scores(self):
        from services.risk_aggregation.app.main import app
        with TestClient(app) as c:
            payload = {
                "client_id": "CL12345",
                "rule_score": 60,
                "ml_probability": 0.75,
                "graph_risk_score": 70,
            }
            resp = c.post("/api/v1/risk/aggregate", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            # Expected: 60*0.5 + 0.75*100*0.3 + 70*0.2 = 30 + 22.5 + 14 = 66.5
            assert abs(data["final_score"] - 66.5) < 0.1
            assert data["risk_rating"] == "HIGH"

    def test_score_capped_at_100(self):
        from services.risk_aggregation.app.main import app
        with TestClient(app) as c:
            payload = {
                "client_id": "CL99999",
                "rule_score": 100,
                "ml_probability": 1.0,
                "graph_risk_score": 100,
            }
            resp = c.post("/api/v1/risk/aggregate", json=payload)
            assert resp.status_code == 200
            assert resp.json()["final_score"] <= 100
