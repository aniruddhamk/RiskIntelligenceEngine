"""
Client Risk API – Risk scoring router.
Exposes POST /api/v1/client-risk/score
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status

from common.models.schemas import ClientRiskRequest, RiskScoreResponse
from common.security.auth import get_current_user, require_permission, TokenPayload
from app.services.orchestrator import RiskOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter()
_orchestrator = RiskOrchestrator()


@router.post(
    "/client-risk/score",
    response_model=RiskScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Score client AML risk",
    description="""
    Runs the full AML risk scoring pipeline for a client:
    1. Feature Engineering
    2. Rule Engine Evaluation
    3. ML Model Scoring
    4. Graph Intelligence Analysis
    5. Weighted Risk Aggregation

    Returns a composite risk score with rating and top risk drivers.
    """,
)
async def score_client_risk(
    request: ClientRiskRequest,
    _user: TokenPayload = Depends(require_permission("score")),
) -> RiskScoreResponse:
    """
    POST /api/v1/client-risk/score

    Orchestrates the complete AML risk scoring pipeline for a client.
    Requires 'score' permission (roles: risk_engine, admin, service).
    """
    try:
        result = await _orchestrator.score_client(request)
        logger.info(
            f"Client {request.client_id} scored: {result.risk_score:.1f} ({result.risk_rating})"
        )
        return result
    except Exception as e:
        logger.error(f"Risk scoring failed for {request.client_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk scoring pipeline failed: {str(e)}",
        )


@router.get(
    "/client-risk/score/{client_id}",
    response_model=RiskScoreResponse,
    summary="Get latest risk score for a client",
)
async def get_client_risk_score(
    client_id: str,
    _user: TokenPayload = Depends(require_permission("view_risk")),
) -> RiskScoreResponse:
    """Placeholder for fetching cached/historical risk score from the score store."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Historical score retrieval not yet implemented. Use POST to compute a fresh score.",
    )
