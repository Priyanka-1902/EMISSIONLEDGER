"""Tenant management endpoints."""
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session, set_tenant_context
from ..dependencies import get_current_user, require_role, AuthenticatedUser
from ..models import TenantDBModel
from shared.schemas.user import UserRole
from shared.schemas.tenant import IndustrySector, TenantTier, TenantStatus

router = APIRouter()


class TenantResponse(BaseModel):
    id: UUID
    slug: str
    legal_name: str
    gstin: str
    city: str
    state: str
    industry_sector: str
    isic_code: str
    tier: str
    status: str
    eu_exporter: bool
    cbam_declarant_id: str | None

    class Config:
        from_attributes = True


class UpdateTenantRequest(BaseModel):
    legal_name: str | None = None
    eu_exporter: bool | None = None
    cbam_declarant_id: str | None = None
    bee_dc_number: str | None = None
    isic_code: str | None = None


@router.get("/me", response_model=TenantResponse)
async def get_my_tenant(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(TenantDBModel).where(TenantDBModel.id == current_user.tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.patch("/me", response_model=TenantResponse)
async def update_my_tenant(
    payload: UpdateTenantRequest,
    current_user: AuthenticatedUser = Depends(require_role(UserRole.ORG_ADMIN)),
    db: AsyncSession = Depends(get_db_session),
):
    await set_tenant_context(db, str(current_user.tenant_id))
    stmt = select(TenantDBModel).where(TenantDBModel.id == current_user.tenant_id)
    tenant = (await db.execute(stmt)).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(tenant, field, value)

    await db.commit()
    await db.refresh(tenant)
    return tenant
