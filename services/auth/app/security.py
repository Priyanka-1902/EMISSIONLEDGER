"""
JWT verification against AWS Cognito JWKS endpoint.
JWKS keys are cached with a 1-hour TTL and refreshed on key rotation.
"""
from __future__ import annotations
import time
from typing import Any
import httpx
from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError, JWTClaimsError
import structlog

from .config import get_settings

log = structlog.get_logger(__name__)

_jwks_cache: dict[str, Any] = {}
_jwks_fetched_at: float = 0.0
_JWKS_TTL = 3600  # 1 hour


async def _get_jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at
    now = time.time()
    if _jwks_cache and (now - _jwks_fetched_at) < _JWKS_TTL:
        return _jwks_cache
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(settings.cognito_jwks_url)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_fetched_at = now
        return _jwks_cache


async def verify_token(token: str) -> dict[str, Any]:
    """
    Verify a Cognito JWT. Returns the decoded claims dict.
    Raises HTTPException-compatible ValueError on failure.
    """
    settings = get_settings()
    try:
        jwks = await _get_jwks()
        # jose will select the correct key by kid header
        claims = jwt.decode(
            token,
            jwks,
            algorithms=[settings.jwt_algorithm],
            audience=settings.cognito_client_id,
            issuer=settings.cognito_issuer,
            options={"verify_exp": True},
        )
        return claims
    except ExpiredSignatureError:
        raise ValueError("Token has expired")
    except JWTClaimsError as e:
        raise ValueError(f"Invalid token claims: {e}")
    except JWTError as e:
        raise ValueError(f"Token verification failed: {e}")


def extract_tenant_id(claims: dict) -> str:
    """Extract tenant_id from custom Cognito claims."""
    tenant_id = claims.get("custom:tenant_id")
    if not tenant_id:
        raise ValueError("Token missing required tenant_id claim")
    return tenant_id


def extract_role(claims: dict) -> str:
    """Extract role from Cognito groups or custom claim."""
    groups = claims.get("cognito:groups", [])
    # Map Cognito group to role — groups are prefixed with tenant slug
    for group in groups:
        for role in ["org_admin", "finance", "plant_manager", "sustainability_officer",
                     "external_auditor", "eu_verifier", "read_only_investor"]:
            if group.endswith(f":{role}"):
                return role
    # Fallback to custom claim
    return claims.get("custom:role", "read_only_investor")
