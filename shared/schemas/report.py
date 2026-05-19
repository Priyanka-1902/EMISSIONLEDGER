from __future__ import annotations
from enum import Enum
from uuid import UUID, uuid4
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class ReportType(str, Enum):
    CBAM_DECLARANT = "cbam_declarant"            # EU CBAM quarterly declarant report
    GHG_PROTOCOL_CORPORATE = "ghg_protocol_corporate"
    BRSR = "brsr"                                 # SEBI BRSR disclosure
    BEE_PAT = "bee_pat"                           # BEE PAT cycle submission
    INDIA_CCTS = "india_ccts"                     # India Carbon Credit Trading Scheme
    INVESTOR_ESG = "investor_esg"
    SUPPLIER_DATA_REQUEST = "supplier_data_request"
    INTERNAL_SUMMARY = "internal_summary"


class ReportStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    VERIFIED = "verified"      # signed off by EU verifier
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ApprovalStep(BaseModel):
    role: str
    user_id: UUID | None = None
    approved_at: datetime | None = None
    signature_hash: str | None = None


class Report(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    report_type: ReportType
    status: ReportStatus = ReportStatus.DRAFT
    title: str
    reporting_period_start: date
    reporting_period_end: date

    # Emissions summary (tCO2e)
    scope_1_tco2e: Decimal = Decimal("0")
    scope_2_tco2e: Decimal = Decimal("0")
    scope_3_tco2e: Decimal = Decimal("0")
    total_tco2e: Decimal = Decimal("0")

    # Data quality
    data_completeness_pct: Decimal = Decimal("0")
    verification_level: str | None = None  # "limited", "reasonable"

    # Storage
    s3_key: str | None = None          # generated report file
    xml_s3_key: str | None = None      # CBAM XML
    signature_hash: str | None = None  # cryptographic signature
    qr_audit_trail: str | None = None  # embedded QR code data

    # Approval chain
    approval_steps: list[ApprovalStep] = Field(default_factory=list)
    submitted_to: str | None = None    # EU CBAM Registry, MoEFCC, etc.
    submission_reference: str | None = None
    submitted_at: datetime | None = None

    # Versioning
    version: int = 1
    parent_report_id: UUID | None = None  # for superseded versions

    # CBAM-specific
    cbam_goods_category: str | None = None  # iron_steel, cement, aluminium, etc.
    cbam_cn_codes: list[str] = Field(default_factory=list)
    cbam_certificate_price_eur: Decimal | None = None
    cbam_financial_exposure_eur: Decimal | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: UUID | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
