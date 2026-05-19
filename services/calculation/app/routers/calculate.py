"""Calculation service API endpoints."""
from __future__ import annotations
from uuid import UUID
from datetime import date
from decimal import Decimal
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..engine.core import GHGCalculator, CalculationInput
from ..engine.cbam import CBAMCalculator, CBAMGoodsLine
from shared.schemas.emission import Scope, ActivityType, CalculationMethod, ConfidenceLevel

router = APIRouter()

_calculator = GHGCalculator()
_cbam_calculator = CBAMCalculator()


class CalculateRequest(BaseModel):
    facility_id: UUID
    activity_date: date
    scope: Scope
    activity_type: ActivityType
    activity_quantity: Decimal = Field(gt=0)
    activity_unit: str
    activity_description: str
    source_system: str = "manual"
    source_record_id: str | None = None
    fuel_type: str | None = None
    grid_region: str | None = None
    calculation_method: CalculationMethod = CalculationMethod.ACTIVITY_BASED
    confidence_level: ConfidenceLevel | None = None


class CalculationResponse(BaseModel):
    record_id: UUID
    tco2e: Decimal
    tco2e_lower: Decimal
    tco2e_upper: Decimal
    confidence_level: str
    factor_name: str
    factor_value: Decimal
    factor_unit: str
    factor_source: str
    factor_version_hash: str
    input_hash: str
    output_hash: str
    scope: str
    activity_type: str


class CBAMCalculateRequest(BaseModel):
    cn_code: str
    goods_description: str
    quantity_tonnes: Decimal = Field(gt=0)
    country_of_origin: str = "IN"
    as_of: date
    cbam_certificate_price_eur: Decimal | None = None
    direct_emissions_tco2e_per_tonne: Decimal | None = None
    uses_default: bool = True


class CBAMCalculationResponse(BaseModel):
    cn_code: str
    goods_category: str
    quantity_tonnes: Decimal
    direct_ee_tco2e: Decimal
    indirect_ee_tco2e: Decimal
    total_ee_tco2e: Decimal
    total_ee_per_tonne: Decimal
    uses_defaults: bool
    default_multiplier: Decimal
    cbam_certificates_required: Decimal
    cbam_financial_exposure_eur: Decimal | None
    methodology_reference: str


@router.post("/", response_model=CalculationResponse, status_code=status.HTTP_201_CREATED)
async def calculate_emission(
    payload: CalculateRequest,
    tenant_id: UUID,  # injected by gateway from JWT
    user_id: UUID,
):
    """
    Calculate GHG emissions for one activity record.
    Returns the full auditable result including factor provenance.
    """
    inp = CalculationInput(
        tenant_id=tenant_id,
        facility_id=payload.facility_id,
        activity_date=payload.activity_date,
        scope=payload.scope,
        activity_type=payload.activity_type,
        activity_quantity=payload.activity_quantity,
        activity_unit=payload.activity_unit,
        activity_description=payload.activity_description,
        source_system=payload.source_system,
        source_record_id=payload.source_record_id,
        fuel_type=payload.fuel_type,
        grid_region=payload.grid_region,
        calculation_method=payload.calculation_method,
        confidence_level=payload.confidence_level,
        created_by=user_id,
    )
    try:
        result, record = _calculator.calculate(inp)
    except KeyError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # TODO: persist record to DB via repository layer

    return CalculationResponse(
        record_id=record.id,
        tco2e=result.tco2e,
        tco2e_lower=result.tco2e_lower,
        tco2e_upper=result.tco2e_upper,
        confidence_level=result.confidence_level.value,
        factor_name=result.factor.name,
        factor_value=result.factor.value,
        factor_unit=result.factor.unit,
        factor_source=result.factor.source.value,
        factor_version_hash=result.factor.version_hash,
        input_hash=result.input_hash,
        output_hash=result.output_hash,
        scope=record.scope.value,
        activity_type=record.activity_type.value,
    )


@router.post("/cbam", response_model=CBAMCalculationResponse)
async def calculate_cbam(
    payload: CBAMCalculateRequest,
    tenant_id: UUID,
):
    """
    Calculate CBAM embedded emissions for one goods line.
    Returns certificate obligation and financial exposure.
    """
    line = CBAMGoodsLine(
        cn_code=payload.cn_code,
        goods_description=payload.goods_description,
        quantity_tonnes=payload.quantity_tonnes,
        country_of_origin=payload.country_of_origin,
        direct_emissions_tco2e_per_tonne=payload.direct_emissions_tco2e_per_tonne,
        uses_default_direct=payload.uses_default,
    )
    try:
        result = _cbam_calculator.calculate_line(
            line=line,
            as_of=payload.as_of,
            cbam_certificate_price_eur=payload.cbam_certificate_price_eur,
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))

    return CBAMCalculationResponse(
        cn_code=result.cn_code,
        goods_category=result.goods_category,
        quantity_tonnes=result.quantity_tonnes,
        direct_ee_tco2e=result.direct_ee_tco2e,
        indirect_ee_tco2e=result.indirect_ee_tco2e,
        total_ee_tco2e=result.total_ee_tco2e,
        total_ee_per_tonne=result.total_ee_per_tonne,
        uses_defaults=result.uses_defaults,
        default_multiplier=result.default_multiplier,
        cbam_certificates_required=result.cbam_certificates_required,
        cbam_financial_exposure_eur=result.cbam_financial_exposure_eur,
        methodology_reference=result.methodology_reference,
    )
