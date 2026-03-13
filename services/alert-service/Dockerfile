FROM python:3.11-slim
WORKDIR /app
COPY services/alert-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY common /common
RUN pip install --no-cache-dir -e /common
COPY services/alert-service/app ./app
EXPOSE 8008
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8008", "--workers", "2"]
