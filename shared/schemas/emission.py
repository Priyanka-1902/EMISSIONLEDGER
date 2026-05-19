from __future__ import annotations
from enum import Enum
from uuid import UUID, uuid4
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class Scope(str, Enum):
    SCOPE_1 = "scope_1"  # Direct combustion, process, fugitive
    SCOPE_2 = "scope_2"  # Purchased electricity, heat, steam
    SCOPE_3 = "scope_3"  # Value chain (15 categories per GHG Protocol)


class ActivityType(str, Enum):
    # Scope 1
    STATIONARY_COMBUSTION = "stationary_combustion"
    MOBILE_COMBUSTION = "mobile_combustion"
    PROCESS_EMISSIONS = "process_emissions"
    FUGITIVE_EMISSIONS = "fugitive_emissions"
    # Scope 2
    PURCHASED_ELECTRICITY = "purchased_electricity"
    PURCHASED_HEAT = "purchased_heat"
    PURCHASED_STEAM = "purchased_steam"
    # Scope 3 categories
    UPSTREAM_TRANSPORT = "upstream_transport"       # Cat 4
    WASTE_OPERATIONS = "waste_operations"           # Cat 5
    BUSINESS_TRAVEL = "business_travel"             # Cat 6
    EMPLOYEE_COMMUTING = "employee_commuting"       # Cat 7
    UPSTREAM_LEASED = "upstream_leased"             # Cat 8
    DOWNSTREAM_TRANSPORT = "downstream_transport"   # Cat 9
    PROCESSING_SOLD = "processing_sold"             # Cat 10
    USE_OF_SOLD = "use_of_sold"                     # Cat 11
    END_OF_LIFE = "end_of_life"                     # Cat 12
    DOWNSTREAM_LEASED = "downstream_leased"         # Cat 13
    FRANCHISES = "franchises"                       # Cat 14
    INVESTMENTS = "investments"                     # Cat 15
    PURCHASED_GOODS = "purchased_goods"             # Cat 1
    CAPITAL_GOODS = "capital_goods"                 # Cat 2
    FUEL_ENERGY_UPSTREAM = "fuel_energy_upstream"   # Cat 3


class CalculationMethod(str, Enum):
    ACTIVITY_BASED = "activity_based"
    SPEND_BASED = "spend_based"
    MASS_BALANCE = "mass_balance"
    DIRECT_MONITORING = "direct_monitoring"
    CBAM_DEFAULT = "cbam_default"
    CBAM_ACTUAL = "cbam_actual"


class ConfidenceLevel(str, Enum):
    HIGH = "high"      # Activity-based with measured data
    MEDIUM = "medium"  # Activity-based with estimated activity
    LOW = "low"        # Spend-based or CBAM defaults


class EmissionRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    facility_id: UUID
    reporting_period_start: date
    reporting_period_end: date
    scope: Scope
    activity_type: ActivityType
    calculation_method: CalculationMethod
    confidence_level: ConfidenceLevel

    # Activity data
    activity_description: str
    activity_quantity: Decimal
    activity_unit: str  # e.g., "kWh", "litre", "tonne", "km"

    # Factor applied
    factor_id: UUID
    factor_value: Decimal
    factor_unit: str  # e.g., "kgCO2e/kWh"
    factor_version_hash: str  # sha256 of factor record for audit

    # Result
    tco2e: Decimal = Field(description="Tonnes CO2 equivalent")
    tco2e_lower: Decimal = Field(description="Lower bound of 95% confidence interval")
    tco2e_upper: Decimal = Field(description="Upper bound of 95% confidence interval")

    # Traceability
    source_record_id: str | None = None  # ID in source system (Tally voucher, etc.)
    source_document_s3_key: str | None = None
    input_hash: str | None = None  # sha256(activity_quantity + factor_id + factor_value)
    output_hash: str | None = None  # sha256(tco2e + input_hash)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: UUID | None = None

    class Config:
        from_attributes = True
