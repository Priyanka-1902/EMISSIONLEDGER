"""
FastAPI dependency injection for authentication and authorisation.
"""
from __future__ import annotations
from uuid import UUID
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .security import verify_token, extract_tenant_id, extract_role
from .database import get_db_session
from .models import UserDBModel
from shared.schemas.user import UserRole, ROLE_PERMISSIONS
import structlog

log = structlog.get_logger(__name__)
bearer = HTTPBearer(auto_error=True)


class AuthenticatedUser:
    def __init__(
        self,
        user_id: UUID,
        tenant_id: UUID,
        cognito_sub: str,
        email: str,
        role: UserRole,
        facility_ids: list[UUID],
    ):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.cognito_sub = cognito_sub
        self.email = email
        self.role = role
        self.facility_ids = facility_ids

    def require_permission(self, permission: str) -> None:
        if permission not in ROLE_PERMISSIONS.get(self.role, set()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{self.role}' does not have permission '{permission}'",
            )

    def can(self, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.role, set())


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    request: Request = None,
    db=Depends(get_db_session),
) -> AuthenticatedUser:
    token = credentials.credentials
    try:
        claims = await verify_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    cognito_sub = claims.get("sub")
    if not cognito_sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: no sub")

    # Load user from DB (validates they still exist and are active)
    from sqlalchemy import select
    stmt = select(UserDBModel).where(UserDBModel.cognito_sub == cognito_sub)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return AuthenticatedUser(
        user_id=user.id,
        tenant_id=user.tenant_id,
        cognito_sub=cognito_sub,
        email=user.email,
        role=UserRole(user.role),
        facility_ids=user.facility_ids or [],
    )


def require_permission(permission: str):
    """Dependency factory for permission-based access control."""
    async def _check(current_user: AuthenticatedUser = Depends(get_current_user)):
        current_user.require_permission(permission)
        return current_user
    return _check


def require_role(*roles: UserRole):
    """Dependency factory for role-based access control."""
    async def _check(current_user: AuthenticatedUser = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {[r.value for r in roles]}",
            )
        return current_user
    return _check
