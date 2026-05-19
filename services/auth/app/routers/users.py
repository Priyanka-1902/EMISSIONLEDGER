"""User management endpoints."""
from __future__ import annotations
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session, set_tenant_context
from ..dependencies import get_current_user, require_permission, AuthenticatedUser
from ..models import UserDBModel
from shared.schemas.user import UserRole

router = APIRouter()


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole
    facility_ids: list[UUID] = []
    cognito_sub: str  # set by Cognito post-confirmation trigger


class UserResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    full_name: str
    role: UserRole
    facility_ids: list[UUID]
    mfa_enabled: bool
    is_active: bool
    last_login: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class UpdateUserRequest(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    facility_ids: list[UUID] | None = None
    is_active: bool | None = None


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: AuthenticatedUser = Depends(get_current_user),
                 db: AsyncSession = Depends(get_db_session)):
    await set_tenant_context(db, str(current_user.tenant_id))
    stmt = select(UserDBModel).where(UserDBModel.id == current_user.user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/", response_model=list[UserResponse])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: AuthenticatedUser = Depends(require_permission("tenant:manage_users")),
    db: AsyncSession = Depends(get_db_session),
):
    await set_tenant_context(db, str(current_user.tenant_id))
    offset = (page - 1) * page_size
    stmt = (
        select(UserDBModel)
        .where(UserDBModel.tenant_id == current_user.tenant_id)
        .order_by(UserDBModel.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserRequest,
    current_user: AuthenticatedUser = Depends(require_permission("tenant:manage_users")),
    db: AsyncSession = Depends(get_db_session),
):
    await set_tenant_context(db, str(current_user.tenant_id))
    # Check email uniqueness within tenant
    stmt = select(UserDBModel).where(
        UserDBModel.tenant_id == current_user.tenant_id,
        UserDBModel.email == payload.email,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="User with this email already exists")

    user = UserDBModel(
        tenant_id=current_user.tenant_id,
        cognito_sub=payload.cognito_sub,
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role.value,
        facility_ids=payload.facility_ids,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    payload: UpdateUserRequest,
    current_user: AuthenticatedUser = Depends(require_permission("tenant:manage_users")),
    db: AsyncSession = Depends(get_db_session),
):
    await set_tenant_context(db, str(current_user.tenant_id))
    stmt = select(UserDBModel).where(
        UserDBModel.id == user_id,
        UserDBModel.tenant_id == current_user.tenant_id,
    )
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role is not None:
        user.role = payload.role.value
    if payload.facility_ids is not None:
        user.facility_ids = payload.facility_ids
    if payload.is_active is not None:
        user.is_active = payload.is_active

    await db.commit()
    await db.refresh(user)
    return user


@router.post("/me/record-login")
async def record_login(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Called by the frontend after successful login to record last_login timestamp."""
    await set_tenant_context(db, str(current_user.tenant_id))
    stmt = (
        update(UserDBModel)
        .where(UserDBModel.id == current_user.user_id)
        .values(last_login=datetime.utcnow())
    )
    await db.execute(stmt)
    await db.commit()
    return {"status": "ok"}
