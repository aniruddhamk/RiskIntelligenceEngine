FROM python:3.11-slim
WORKDIR /app
COPY services/ml-scoring/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY common /common
RUN pip install --no-cache-dir -e /common
COPY services/ml-scoring/app ./app
# Create model directory
RUN mkdir -p app/models/saved
EXPOSE 8005
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8005/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
