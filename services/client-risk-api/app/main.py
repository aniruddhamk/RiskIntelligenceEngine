"""
Client Risk API – FastAPI application entry point.
Primary external-facing service for risk scoring.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import risk, health

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s – %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Client Risk API starting up...")
    yield
    logger.info("🛑 Client Risk API shutting down...")


app = FastAPI(
    title="Client Risk API",
    description="Enterprise AML Risk Scoring – Client onboarding and risk assessment",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "path": str(request.url.path)},
    )


app.include_router(health.router, tags=["Health"])
app.include_router(risk.router, prefix="/api/v1", tags=["Client Risk Scoring"])
