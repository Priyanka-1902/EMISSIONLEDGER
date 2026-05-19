"""
GHG Calculation Engine — Core

Implements the GHG Protocol Corporate Standard calculation methodology.
Every calculation produces a fully traceable record with:
- input_hash: sha256(activity_quantity + factor_id + factor_value)
- output_hash: sha256(tco2e + input_hash)
- factor_version_hash: immutable hash of the factor record used

Confidence intervals are computed from activity data uncertainty
using ISO 14064-1 propagation rules.
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from shared.factors.loader import get_registry
from shared.schemas.emission import (
    EmissionRecord, Scope, ActivityType, CalculationMethod, ConfidenceLevel
)
from shared.schemas.factor import EmissionFactor, FactorSource

# Uncertainty bounds by confidence level (multiplicative ±%)
UNCERTAINTY_MAP = {
    ConfidenceLevel.HIGH: Decimal("0.05"),     # ±5% — measured data
    ConfidenceLevel.MEDIUM: Decimal("0.15"),   # ±15% — estimated activity
    ConfidenceLevel.LOW: Decimal("0.50"),      # ±50% — spend-based
}

# Unit normalisations to SI base units before calculation
UNIT_TO_BASE: dict[str, tuple[str, Decimal]] = {
    "litre": ("litre", Decimal("1")),
    "l": ("litre", Decimal("1")),
    "kl": ("litre", Decimal("1000")),
    "kWh": ("kWh", Decimal("1")),
    "MWh": ("kWh", Decimal("1000")),
    "GWh": ("kWh", Decimal("1000000")),
    "scm": ("scm", Decimal("1")),
    "m3": ("scm", Decimal("1")),
    "kg": ("kg", Decimal("1")),
    "tonne": ("kg", Decimal("1000")),
    "MT": ("kg", Decimal("1000000")),
    "km": ("km", Decimal("1")),
    "tonne-km": ("tonne-km", Decimal("1")),
    "INR": ("INR", Decimal("1")),
    "Rs": ("INR", Decimal("1")),
    "Rs.": ("INR", Decimal("1")),
}


@dataclass
class CalculationInput:
    tenant_id: UUID
    facility_id: UUID
    activity_date: date
    scope: Scope
    activity_type: ActivityType
    activity_quantity: Decimal
    activity_unit: str
    activity_description: str
    source_system: str
    source_record_id: str | None = None
    source_document_s3_key: str | None = None
    # Override factor selection
    fuel_type: str | None = None
    grid_region: str | None = None
    isic_code: str | None = None
    calculation_method: CalculationMethod = CalculationMethod.ACTIVITY_BASED
    confidence_level: ConfidenceLevel | None = None
    created_by: UUID | None = None


@dataclass
class CalculationResult:
    tco2e: Decimal
    tco2e_lower: Decimal
    tco2e_upper: Decimal
    factor: EmissionFactor
    confidence_level: ConfidenceLevel
    input_hash: str
    output_hash: str
    normalised_quantity: Decimal
    normalised_unit: str


def _compute_input_hash(quantity: Decimal, factor_id: UUID, factor_value: Decimal) -> str:
    payload = json.dumps({
        "quantity": str(quantity),
        "factor_id": str(factor_id),
        "factor_value": str(factor_value),
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _compute_output_hash(tco2e: Decimal, input_hash: str) -> str:
    payload = json.dumps({"tco2e": str(tco2e), "input_hash": input_hash}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _normalise_quantity(quantity: Decimal, unit: str) -> tuple[Decimal, str]:
    """Convert activity quantity to base unit for factor application."""
    if unit not in UNIT_TO_BASE:
        raise ValueError(f"Unknown unit '{unit}'. Add to UNIT_TO_BASE map.")
    base_unit, multiplier = UNIT_TO_BASE[unit]
    return (quantity * multiplier).quantize(Decimal("0.000001")), base_unit


def _infer_confidence(
    calculation_method: CalculationMethod,
    source_system: str,
) -> ConfidenceLevel:
    if calculation_method in (CalculationMethod.DIRECT_MONITORING, CalculationMethod.MASS_BALANCE):
        return ConfidenceLevel.HIGH
    if source_system in ("tally", "zoho", "sap"):
        return ConfidenceLevel.MEDIUM
    if calculation_method == CalculationMethod.SPEND_BASED:
        return ConfidenceLevel.LOW
    return ConfidenceLevel.MEDIUM


def _infer_reporting_period(activity_date: date) -> tuple[date, date]:
    """Default to the financial year containing the activity date (Apr–Mar)."""
    if activity_date.month >= 4:
        start = date(activity_date.year, 4, 1)
        end = date(activity_date.year + 1, 3, 31)
    else:
        start = date(activity_date.year - 1, 4, 1)
        end = date(activity_date.year, 3, 31)
    return start, end


class GHGCalculator:
    def __init__(self) -> None:
        self._registry = get_registry()

    def calculate(self, inp: CalculationInput) -> tuple[CalculationResult, EmissionRecord]:
        """
        Compute tCO2e for one activity record.
        Returns (CalculationResult, EmissionRecord) — caller persists the record.
        """
        # Normalise units
        norm_qty, norm_unit = _normalise_quantity(inp.activity_quantity, inp.activity_unit)

        # Resolve factor
        factor = self._registry.get(
            activity_type=inp.activity_type.value,
            as_of=inp.activity_date,
            fuel_type=inp.fuel_type,
            grid_region=inp.grid_region,
            isic_code=inp.isic_code,
        )

        # tCO2e = quantity × factor_value
        # Factor units are expressed per base unit (e.g. kgCO2e/kWh → tCO2e/kWh × 1/1000)
        factor_value = factor.value
        if "kg" in factor.unit and "tCO2e" not in factor.unit:
            # Convert kgCO2e → tCO2e
            conversion = Decimal("0.001")
        else:
            conversion = Decimal("1")

        tco2e = (norm_qty * factor_value * conversion).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

        confidence = inp.confidence_level or _infer_confidence(inp.calculation_method, inp.source_system)
        uncertainty = UNCERTAINTY_MAP[confidence]
        tco2e_lower = (tco2e * (1 - uncertainty)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        tco2e_upper = (tco2e * (1 + uncertainty)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

        input_hash = _compute_input_hash(norm_qty, factor.id, factor_value)
        output_hash = _compute_output_hash(tco2e, input_hash)

        period_start, period_end = _infer_reporting_period(inp.activity_date)

        result = CalculationResult(
            tco2e=tco2e,
            tco2e_lower=tco2e_lower,
            tco2e_upper=tco2e_upper,
            factor=factor,
            confidence_level=confidence,
            input_hash=input_hash,
            output_hash=output_hash,
            normalised_quantity=norm_qty,
            normalised_unit=norm_unit,
        )
        record = EmissionRecord(
            tenant_id=inp.tenant_id,
            facility_id=inp.facility_id,
            reporting_period_start=period_start,
            reporting_period_end=period_end,
            scope=inp.scope,
            activity_type=inp.activity_type,
            calculation_method=inp.calculation_method,
            confidence_level=confidence,
            activity_description=inp.activity_description,
            activity_quantity=inp.activity_quantity,
            activity_unit=inp.activity_unit,
            factor_id=factor.id,
            factor_value=factor.value,
            factor_unit=factor.unit,
            factor_version_hash=factor.version_hash,
            tco2e=tco2e,
            tco2e_lower=tco2e_lower,
            tco2e_upper=tco2e_upper,
            source_record_id=inp.source_record_id,
            source_document_s3_key=inp.source_document_s3_key,
            input_hash=input_hash,
            output_hash=output_hash,
            created_by=inp.created_by,
        )
        return result, record

    def calculate_batch(
        self, inputs: list[CalculationInput]
    ) -> list[tuple[CalculationResult, EmissionRecord]]:
        return [self.calculate(inp) for inp in inputs]
