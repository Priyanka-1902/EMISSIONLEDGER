"""SQLAlchemy models local to the auth service."""
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class TenantDBModel(Base):
    __tablename__ = "tenants"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(63), nullable=False)
    legal_name = Column(String(255), nullable=False)
    gstin = Column(String(15), nullable=False)
    pan = Column(String(10), nullable=False)
    registered_address = Column(Text, nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    pincode = Column(String(10), nullable=False)
    country = Column(String(2), nullable=False, default="IN")
    industry_sector = Column(String(50), nullable=False)
    isic_code = Column(String(4), nullable=False)
    tier = Column(String(20), nullable=False, default="entry")
    status = Column(String(20), nullable=False, default="onboarding")
    kms_key_arn = Column(String(255))
    eu_exporter = Column(Boolean, nullable=False, default=False)
    cbam_declarant_id = Column(String(100))
    bee_dc_number = Column(String(100))
    settings = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class UserDBModel(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    cognito_sub = Column(String(255), nullable=False, unique=True)
    email = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    facility_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    mfa_enabled = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
