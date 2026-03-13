FROM python:3.11-slim
WORKDIR /app
COPY services/feature-engineering/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY common /common
RUN pip install --no-cache-dir -e /common
COPY services/feature-engineering/app ./app
EXPOSE 8003
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003", "--workers", "2"]
