"""
Security utilities: JWT validation, RBAC, OAuth2 scheme.
"""
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

from common.config import get_settings

logger = logging.getLogger(__name__)
security = HTTPBearer()


# ─── RBAC Roles ──────────────────────────────────────────────────────────────

class Role(str, Enum):
    RISK_ENGINE = "risk_engine"
    COMPLIANCE = "compliance"
    AUDITOR = "auditor"
    ADMIN = "admin"
    SERVICE = "service"  # Internal service-to-service


ROLE_PERMISSIONS = {
    Role.ADMIN: {"score", "view_risk", "audit_logs", "manage_alerts", "manage_rules"},
    Role.RISK_ENGINE: {"score", "view_risk"},
    Role.COMPLIANCE: {"view_risk", "manage_alerts"},
    Role.AUDITOR: {"audit_logs", "view_risk"},
    Role.SERVICE: {"score", "view_risk", "create_alert"},
}


# ─── Token Models ────────────────────────────────────────────────────────────

class TokenPayload(BaseModel):
    sub: str
    role: Role
    exp: Optional[datetime] = None
    iat: Optional[datetime] = None


# ─── Token Creation ──────────────────────────────────────────────────────────

def create_access_token(subject: str, role: Role, expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    payload = {
        "sub": subject,
        "role": role.value,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


# ─── Token Validation ────────────────────────────────────────────────────────

def decode_token(token: str) -> TokenPayload:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return TokenPayload(
            sub=payload["sub"],
            role=Role(payload["role"]),
            exp=payload.get("exp"),
        )
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── FastAPI Dependencies ─────────────────────────────────────────────────────

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> TokenPayload:
    """FastAPI dependency – validates JWT and returns TokenPayload."""
    return decode_token(credentials.credentials)


def require_permission(permission: str):
    """Dependency factory that checks a specific permission."""
    def _check(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        allowed = ROLE_PERMISSIONS.get(user.role, set())
        if permission not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' lacks permission '{permission}'",
            )
        return user
    return _check


# ─── Service Token (internal) ─────────────────────────────────────────────────

def get_service_token() -> str:
    """Generate an internal service-to-service JWT."""
    return create_access_token(subject="internal-service", role=Role.SERVICE)
