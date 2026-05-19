from __future__ import annotations
from enum import Enum
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr


class TenantTier(str, Enum):
    ENTRY = "entry"        # Rs. 12,000/year — core CBAM + GHG
    GROWTH = "growth"      # Rs. 28,000/year — + BRSR + BEE/PAT
    ENTERPRISE = "enterprise"  # Rs. 60,000/year — + carbon credits + SSO + API


class TenantStatus(str, Enum):
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    OFFBOARDED = "offboarded"


class IndustrySector(str, Enum):
    TEXTILES = "textiles"
    PHARMACEUTICALS = "pharmaceuticals"
    AUTO_COMPONENTS = "auto_components"
    STEEL = "steel"
    CEMENT = "cement"
    ALUMINIUM = "aluminium"
    FERTILISERS = "fertilisers"
    OTHER = "other"


class Tenant(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    slug: str = Field(..., pattern=r"^[a-z0-9-]{3,63}$")  # used for subdomain
    legal_name: str
    gstin: str = Field(..., pattern=r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
    pan: str = Field(..., pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")
    registered_address: str
    city: str
    state: str
    pincode: str
    country: str = "IN"
    industry_sector: IndustrySector
    isic_code: str = Field(..., description="4-digit ISIC Rev.4 code")
    tier: TenantTier = TenantTier.ENTRY
    status: TenantStatus = TenantStatus.ONBOARDING
    kms_key_arn: str | None = None  # per-tenant encryption key
    eu_exporter: bool = False
    cbam_declarant_id: str | None = None  # EU CBAM registry ID when issued
    bee_dc_number: str | None = None  # BEE Designated Consumer number
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
