.PHONY: dev stop build test test-coverage lint format clean k8s-deploy help

help:
	@echo "╔══════════════════════════════════════════════╗"
	@echo "║   RiskIntelligenceEngine – Makefile          ║"
	@echo "╚══════════════════════════════════════════════╝"
	@echo ""
	@echo "  make dev          Start all services (docker-compose)"
	@echo "  make stop         Stop all services"  
	@echo "  make build        Build all Docker images"
	@echo "  make test         Run all unit tests"
	@echo "  make test-cov     Run tests with coverage"
	@echo "  make lint         Run flake8 linter"
	@echo "  make format       Format code with black"
	@echo "  make k8s-deploy   Deploy to Kubernetes"
	@echo "  make clean        Remove containers and volumes"

dev:
	docker-compose up -d
	@echo "✅ All services started."
	@echo "   API Gateway:         http://localhost:8000"
	@echo "   Client Risk API:     http://localhost:8001/docs"
	@echo "   Transaction API:     http://localhost:8002/docs"
	@echo "   Feature Engineering: http://localhost:8003/docs"
	@echo "   Rule Engine:         http://localhost:8004/docs"
	@echo "   ML Scoring:          http://localhost:8005/docs"
	@echo "   Graph Intelligence:  http://localhost:8006/docs"
	@echo "   Risk Aggregation:    http://localhost:8007/docs"
	@echo "   Alert Service:       http://localhost:8008/docs"
	@echo "   Audit Service:       http://localhost:8009/docs"
	@echo "   Neo4j Browser:       http://localhost:7474"

stop:
	docker-compose down

build:
	docker-compose build --no-cache

test:
	@echo "Running tests for all services..."
	@for svc in client-risk-api transaction-risk-api feature-engineering rule-engine ml-scoring graph-intelligence risk-aggregation alert-service audit-service; do \
		echo "\n──── Testing $$svc ────"; \
		cd services/$$svc && pip install -q -r requirements.txt && python -m pytest tests/ -v --tb=short 2>&1 || true; \
		cd ../..; \
	done

test-cov:
	@for svc in client-risk-api transaction-risk-api feature-engineering rule-engine ml-scoring graph-intelligence risk-aggregation alert-service audit-service; do \
		echo "\n──── Coverage: $$svc ────"; \
		cd services/$$svc && python -m pytest tests/ --cov=app --cov-report=term-missing 2>&1 || true; \
		cd ../..; \
	done

lint:
	flake8 services/ common/ --max-line-length=120 --exclude=services/*/app/models/saved

format:
	black services/ common/ --line-length=120

clean:
	docker-compose down -v --remove-orphans
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

k8s-deploy:
	kubectl apply -f k8s/
	@echo "✅ Deployed to Kubernetes"

logs:
	docker-compose logs -f --tail=100

seed:
	python scripts/seed_data.py
