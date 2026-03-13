FROM python:3.11-slim
WORKDIR /app

# Install service dependencies
COPY services/client-risk-api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install common library from repo root
COPY common /common
RUN pip install --no-cache-dir -e /common

# Copy service code
COPY services/client-risk-api/app ./app

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
