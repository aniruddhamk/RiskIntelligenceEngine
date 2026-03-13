FROM python:3.11-slim
WORKDIR /app
COPY services/transaction-risk-api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY common /common
RUN pip install --no-cache-dir -e /common
COPY services/transaction-risk-api/app ./app
EXPOSE 8002
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8002/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "2"]
