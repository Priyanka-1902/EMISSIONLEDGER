from __future__ import annotations
from enum import Enum
from uuid import UUID, uuid4
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class FactorSource(str, Enum):
    CEA_CO2_BASELINE = "cea_co2_baseline"        # CEA CO2 Baseline Database for Indian grid
    BEE_PAT = "bee_pat"                           # Bureau of Energy Efficiency PAT cycles
    IPCC_AR6 = "ipcc_ar6"                         # IPCC Sixth Assessment Report
    DEFRA = "defra"                               # UK DEFRA conversion factors
    EU_CBAM_DEFAULT = "eu_cbam_default"           # EU CBAM Implementing Regulation defaults
    EU_CBAM_ACTUAL = "eu_cbam_actual"             # Verified actuals under CBAM
    ECOINVENT = "ecoinvent"                       # ecoinvent LCI database
    NIST = "nist"                                 # NIST reference values (unit conversions)
    GHG_PROTOCOL = "ghg_protocol"                # GHG Protocol emission factors
    CUSTOM_VERIFIED = "custom_verified"           # Supplier-specific verified factors


class GasType(str, Enum):
    CO2 = "CO2"
    CH4 = "CH4"
    N2O = "N2O"
    HFC = "HFC"
    PFC = "PFC"
    SF6 = "SF6"
    NF3 = "NF3"
    CO2E = "CO2e"  # pre-converted to CO2 equivalent


class EmissionFactor(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str

    # What this factor applies to
    activity_type: str  # maps to ActivityType
    fuel_type: str | None = None
    grid_region: str | None = None  # for electricity factors (state/national)
    isic_code: str | None = None  # for spend-based factors

    # The factor value
    gas_type: GasType = GasType.CO2E
    value: Decimal
    unit: str  # e.g., "kgCO2e/kWh", "kgCO2e/litre", "kgCO2e/Rs"
    gwp_basis: str = "AR6"  # Global Warming Potential basis year

    # Provenance — every factor must be traceable
    source: FactorSource
    source_publication: str  # Full citation
    source_url: str | None = None
    source_page: str | None = None
    effective_from: date
    effective_to: date | None = None  # None = still current
    published_date: date

    # Versioning
    version: str  # semantic version e.g. "2.1.0"
    version_hash: str  # sha256 of (source + value + unit + effective_from)
    superseded_by: UUID | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    approved_by: str | None = None  # email of compliance officer who approved

    class Config:
        from_attributes = True
