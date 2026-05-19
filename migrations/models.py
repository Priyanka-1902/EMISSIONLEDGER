"""
SQLAlchemy ORM models — source of truth for the database schema.
All tables include tenant_id for row-level security.
TimescaleDB hypertables are created via migration scripts, not ORM.
"""
from __future__ import annotations
import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Numeric, Date, DateTime,
    ForeignKey, Enum as SAEnum, Index, UniqueConstraint, CheckConstraint,
    JSON, LargeBinary,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


# ── Tenants ───────────────────────────────────────────────────────────────────

class TenantModel(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(63), unique=True, nullable=False, index=True)
    legal_name = Column(String(255), nullable=False)
    gstin = Column(String(15), unique=True, nullable=False)
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

    users = relationship("UserModel", back_populates="tenant", lazy="dynamic")
    facilities = relationship("FacilityModel", back_populates="tenant", lazy="dynamic")
    emission_records = relationship("EmissionRecordModel", back_populates="tenant", lazy="dynamic")
    reports = relationship("ReportModel", back_populates="tenant", lazy="dynamic")


# ── Users ─────────────────────────────────────────────────────────────────────

class UserModel(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    cognito_sub = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    facility_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    mfa_enabled = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    tenant = relationship("TenantModel", back_populates="users")

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        Index("ix_users_tenant_id_role", "tenant_id", "role"),
    )


# ── Facilities ────────────────────────────────────────────────────────────────

class FacilityModel(Base):
    __tablename__ = "facilities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    address = Column(Text, nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    pincode = Column(String(10), nullable=False)
    grid_region = Column(String(50))  # CEA grid region for electricity factors
    discom = Column(String(100))      # electricity distributor
    discom_consumer_number = Column(String(100))
    naics_code = Column(String(10))
    is_designated_consumer = Column(Boolean, default=False)  # BEE DC status
    annual_energy_tep = Column(Numeric(12, 2))  # Tonnes of oil equivalent
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    tenant = relationship("TenantModel", back_populates="facilities")
    emission_records = relationship("EmissionRecordModel", back_populates="facility", lazy="dynamic")

    __table_args__ = (
        Index("ix_facilities_tenant_id", "tenant_id"),
    )


# ── Emission Records (TimescaleDB hypertable on activity_date) ────────────────

class EmissionRecordModel(Base):
    __tablename__ = "emission_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id"), nullable=False, index=True)
    activity_date = Column(Date, nullable=False)  # hypertable partition key
    reporting_period_start = Column(Date, nullable=False)
    reporting_period_end = Column(Date, nullable=False)
    scope = Column(String(10), nullable=False)
    activity_type = Column(String(50), nullable=False)
    calculation_method = Column(String(30), nullable=False)
    confidence_level = Column(String(10), nullable=False)

    # Activity data
    activity_description = Column(Text, nullable=False)
    activity_quantity = Column(Numeric(20, 6), nullable=False)
    activity_unit = Column(String(30), nullable=False)

    # Factor applied
    factor_id = Column(UUID(as_uuid=True), nullable=False)
    factor_value = Column(Numeric(20, 10), nullable=False)
    factor_unit = Column(String(50), nullable=False)
    factor_version_hash = Column(String(64), nullable=False)

    # Result
    tco2e = Column(Numeric(20, 6), nullable=False)
    tco2e_lower = Column(Numeric(20, 6), nullable=False)
    tco2e_upper = Column(Numeric(20, 6), nullable=False)

    # Traceability
    source_record_id = Column(String(255))
    source_system = Column(String(50))  # tally, zoho, sap, csv, manual
    source_document_s3_key = Column(String(500))
    input_hash = Column(String(64), nullable=False)
    output_hash = Column(String(64), nullable=False)

    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    tenant = relationship("TenantModel", back_populates="emission_records")
    facility = relationship("FacilityModel", back_populates="emission_records")

    __table_args__ = (
        Index("ix_emission_records_tenant_date", "tenant_id", "activity_date"),
        Index("ix_emission_records_tenant_scope", "tenant_id", "scope"),
        Index("ix_emission_records_tenant_period", "tenant_id", "reporting_period_start", "reporting_period_end"),
        CheckConstraint("tco2e >= 0", name="ck_emission_records_tco2e_positive"),
        CheckConstraint("tco2e_lower <= tco2e", name="ck_emission_records_lower_lte_tco2e"),
        CheckConstraint("tco2e_upper >= tco2e", name="ck_emission_records_upper_gte_tco2e"),
    )


# ── Emission Factors (versioned, immutable) ───────────────────────────────────

class EmissionFactorModel(Base):
    __tablename__ = "emission_factors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    activity_type = Column(String(50), nullable=False, index=True)
    fuel_type = Column(String(50))
    grid_region = Column(String(50))
    isic_code = Column(String(10))
    gas_type = Column(String(10), nullable=False, default="CO2e")
    value = Column(Numeric(20, 10), nullable=False)
    unit = Column(String(50), nullable=False)
    gwp_basis = Column(String(10), nullable=False, default="AR6")
    source = Column(String(50), nullable=False)
    source_publication = Column(Text, nullable=False)
    source_url = Column(String(500))
    source_page = Column(String(50))
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    published_date = Column(Date, nullable=False)
    version = Column(String(20), nullable=False)
    version_hash = Column(String(64), nullable=False, unique=True)
    superseded_by = Column(UUID(as_uuid=True), ForeignKey("emission_factors.id"))
    approved_by = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_emission_factors_activity_type_effective", "activity_type", "effective_from", "effective_to"),
    )


# ── Reports ───────────────────────────────────────────────────────────────────

class ReportModel(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    report_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    title = Column(String(500), nullable=False)
    reporting_period_start = Column(Date, nullable=False)
    reporting_period_end = Column(Date, nullable=False)

    scope_1_tco2e = Column(Numeric(20, 6), nullable=False, default=0)
    scope_2_tco2e = Column(Numeric(20, 6), nullable=False, default=0)
    scope_3_tco2e = Column(Numeric(20, 6), nullable=False, default=0)
    total_tco2e = Column(Numeric(20, 6), nullable=False, default=0)

    data_completeness_pct = Column(Numeric(5, 2), nullable=False, default=0)
    verification_level = Column(String(20))

    s3_key = Column(String(500))
    xml_s3_key = Column(String(500))
    signature_hash = Column(String(128))
    qr_audit_trail = Column(Text)

    approval_steps = Column(JSONB, nullable=False, default=list)
    submitted_to = Column(String(255))
    submission_reference = Column(String(255))
    submitted_at = Column(DateTime(timezone=True))

    version = Column(Integer, nullable=False, default=1)
    parent_report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id"))

    # CBAM-specific
    cbam_goods_category = Column(String(50))
    cbam_cn_codes = Column(ARRAY(String), nullable=False, default=list)
    cbam_certificate_price_eur = Column(Numeric(10, 2))
    cbam_financial_exposure_eur = Column(Numeric(20, 2))
    uses_cbam_defaults = Column(Boolean, default=False)
    cbam_declarant_id = Column(String(100))

    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    tenant = relationship("TenantModel", back_populates="reports")

    __table_args__ = (
        Index("ix_reports_tenant_type_period", "tenant_id", "report_type", "reporting_period_start"),
        Index("ix_reports_tenant_status", "tenant_id", "status"),
    )


# ── Audit Log (append-only, hash-chained) ─────────────────────────────────────

class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    sequence_number = Column(Integer, nullable=False)  # per-tenant sequence
    event_type = Column(String(100), nullable=False)
    actor_id = Column(UUID(as_uuid=True))
    actor_email = Column(String(255))
    resource_type = Column(String(100))
    resource_id = Column(String(255))
    action = Column(String(50), nullable=False)  # create, read, update, delete, export, login
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    payload_hash = Column(String(64))  # sha256 of the event payload
    previous_hash = Column(String(64))  # hash of previous entry (chain)
    chain_hash = Column(String(64), nullable=False)  # sha256(payload_hash + previous_hash + sequence)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_logs_tenant_resource", "tenant_id", "resource_type", "resource_id"),
        UniqueConstraint("tenant_id", "sequence_number", name="uq_audit_logs_tenant_sequence"),
    )


# ── Data Ingestion Records ────────────────────────────────────────────────────

class IngestionJobModel(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    source_system = Column(String(50), nullable=False)  # tally, zoho, sap, csv, discom
    status = Column(String(20), nullable=False, default="pending")
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    records_processed = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    error_summary = Column(JSONB, default=dict)
    s3_source_key = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    __table_args__ = (
        Index("ix_ingestion_jobs_tenant_status", "tenant_id", "status"),
    )


# ── Compliance Rules (versioned) ──────────────────────────────────────────────

class ComplianceRuleModel(Base):
    __tablename__ = "compliance_rules"

    id = Column(String(50), primary_key=True)  # e.g. "CBAM-001"
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(30), nullable=False)
    severity = Column(String(10), nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date)
    version = Column(String(20), nullable=False)
    version_hash = Column(String(64), nullable=False)
    regulation_reference = Column(String(500), nullable=False)
    condition = Column(JSONB, nullable=False)
    message_template = Column(Text, nullable=False)
    remediation_url = Column(String(500))
    approved_by = Column(String(255))
    approved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
