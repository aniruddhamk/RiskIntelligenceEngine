# 🛡️ RiskIntelligenceEngine

> **Enterprise Anti-Money Laundering (AML) Risk Platform** — Event-driven microservices with real-time ML scoring, graph-based financial crime detection, configurable rule engine, and regulatory compliance tooling.

[![CI](https://github.com/aniruddhamk/RiskIntelligenceEngine/actions/workflows/ci.yml/badge.svg)](https://github.com/aniruddhamk/RiskIntelligenceEngine/actions)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green.svg)](https://fastapi.tiangolo.com)
[![Kafka](https://img.shields.io/badge/Kafka-3.6-orange.svg)](https://kafka.apache.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📐 Architecture Overview

```
                External Systems
     ─────────────────────────────────────
     │ KYC │ Core Banking │ Payments │ Trade │
     ─────────────────────────────────────
                       │
                  API Gateway (:8000)
                       │
          ─────────────────────────────
          │                           │
  Client Risk API (:8001)   Transaction Risk API (:8002)
          │                           │
          ─────────────────────────────
                       │
                 Kafka Event Bus
                       │
   ────────────────────────────────────────────
   │           │           │         │         │
Feature     Rule       ML Score  Graph    Alert
Engineering Engine     Service   Intel.   Engine
(:8003)    (:8004)    (:8005)   (:8006)  (:8008)
   │           │           │         │         │
   ──────────────── Risk Aggregation ──────────
                       (:8007)
                          │
                  Risk Score Store (PostgreSQL)
                          │
                Monitoring / Compliance UI
```

## 🧩 Microservices

| Service | Port | Responsibility |
|---------|------|----------------|
| `api-gateway` | 8000 | Nginx reverse proxy |
| `client-risk-api` | 8001 | Client onboarding & risk scoring |
| `transaction-risk-api` | 8002 | Real-time transaction monitoring |
| `feature-engineering` | 8003 | ML feature vector generation |
| `rule-engine` | 8004 | Configurable AML rule evaluation |
| `ml-scoring` | 8005 | XGBoost + Random Forest ensemble |
| `graph-intelligence` | 8006 | Network/graph risk analysis |
| `risk-aggregation` | 8007 | Weighted score combination |
| `alert-service` | 8008 | Alert generation & management |
| `audit-service` | 8009 | Regulatory audit logging |

## 📨 Kafka Topics

| Topic | Purpose |
|-------|---------|
| `client_onboarded` | New client created |
| `transaction_event` | Financial transaction |
| `kyc_updated` | KYC data changes |
| `risk_score_generated` | Scoring results |
| `suspicious_activity` | High-risk alerts |

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- GitHub CLI (optional)

### Run Locally

```bash
# Clone
git clone https://github.com/aniruddhamk/RiskIntelligenceEngine.git
cd RiskIntelligenceEngine

# Copy environment config
cp .env.example .env

# Start all services
make dev

# Check health
curl http://localhost:8001/health
```

### Run a Risk Score
```bash
curl -X POST http://localhost:8001/api/v1/client-risk/score \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "clientId": "CL12345",
    "clientType": "CORPORATE",
    "country": "AE",
    "industry": "Trading",
    "pepFlag": false,
    "transactions": {
      "monthlyVolume": 15000000,
      "internationalRatio": 0.65,
      "cashRatio": 0.08
    }
  }'
```

Expected response:
```json
{
  "clientId": "CL12345",
  "riskScore": 67,
  "riskRating": "HIGH",
  "ruleScore": 60,
  "mlProbability": 0.75,
  "graphRiskScore": 70,
  "topRiskDrivers": [
    "High cross-border transactions",
    "Network connection to risky entity",
    "Industry risk"
  ],
  "modelVersion": "AML_GB_v4.1",
  "timestamp": "2026-03-12T15:30:00Z"
}
```

## 📊 Risk Rating Scale

| Score | Rating |
|-------|--------|
| 0–30 | 🟢 Low |
| 31–60 | 🟡 Medium |
| 61–80 | 🔴 High |
| 81–100 | 🚨 Critical |

## 🔐 Security

- OAuth2 + JWT Bearer tokens
- TLS 1.3 in production
- RBAC roles: `risk_engine`, `compliance`, `auditor`
- Field-level encryption for sensitive PII

## 🗂️ Project Structure

```
RiskIntelligenceEngine/
├── common/               # Shared library (schemas, Kafka, security, DB)
├── services/
│   ├── client-risk-api/
│   ├── transaction-risk-api/
│   ├── feature-engineering/
│   ├── rule-engine/
│   ├── ml-scoring/
│   ├── graph-intelligence/
│   ├── risk-aggregation/
│   ├── alert-service/
│   └── audit-service/
├── kafka/                # Topic definitions & schemas
├── k8s/                  # Kubernetes manifests
├── scripts/              # Developer utilities
└── docker-compose.yml
```

## 🧪 Testing

```bash
make test             # All services
make test-coverage    # With coverage report
```

## ☁️ Deployment

```bash
# Kubernetes
kubectl apply -f k8s/
# or
make k8s-deploy
```

## 📜 License

MIT © 2026 RiskIntelligenceEngine Contributors
