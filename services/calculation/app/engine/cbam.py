"""
EU CBAM Embedded Emissions Calculator

Implements the methodology from Commission Implementing Regulation (EU) 2023/1773.

Direct Embedded Emissions (DEE) = Σ (process emissions from production)
Indirect Embedded Emissions (IEE) = electricity_consumed × grid_emission_factor
Total Embedded Emissions (TEE) = DEE + IEE (for goods where both apply)

For upstream goods: TEE includes precursor embedded emissions per tonne.

Reference: Implementing Regulation (EU) 2023/1773, Annex III, Section 2.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from datetime import date

from shared.factors.loader import get_registry
from shared.schemas.factor import FactorSource


# CBAM goods categories and their CN code ranges
CBAM_GOODS_CATEGORIES = {
    "iron_and_steel": {
        "cn_prefixes": ["7206", "7207", "7208", "7209", "7210", "7211", "7212", "7213", "7214", "7215", "7216", "7217", "7301", "7302", "7303", "7304", "7305", "7306"],
        "includes_indirect": True,
        "methodology": "Annex III Section 4",
    },
    "cement": {
        "cn_prefixes": ["2523"],
        "includes_indirect": False,
        "methodology": "Annex III Section 5",
    },
    "aluminium": {
        "cn_prefixes": ["7601", "7602", "7604", "7605", "7606", "7607", "7608", "7609"],
        "includes_indirect": True,
        "methodology": "Annex III Section 6",
    },
    "fertilisers": {
        "cn_prefixes": ["2808", "2814", "3102", "3103", "3104", "3105"],
        "includes_indirect": False,
        "methodology": "Annex III Section 7",
    },
    "hydrogen": {
        "cn_prefixes": ["2804"],
        "includes_indirect": False,
        "methodology": "Annex III Section 8",
    },
    "electricity": {
        "cn_prefixes": ["2716"],
        "includes_indirect": False,
        "methodology": "Annex III Section 3",
    },
}


@dataclass
class CBAMGoodsLine:
    """One line of CBAM goods in an import shipment."""
    cn_code: str
    goods_description: str
    quantity_tonnes: Decimal
    country_of_origin: str
    producer_name: str | None = None

    # Direct emissions — from producer data or defaults
    direct_emissions_tco2e_per_tonne: Decimal | None = None
    uses_default_direct: bool = True

    # Indirect emissions (where applicable)
    electricity_kwh_per_tonne: Decimal | None = None
    grid_emission_factor_tco2e_per_kwh: Decimal | None = None
    uses_default_indirect: bool = True

    # Domestic carbon price paid (Art. 9 deduction)
    domestic_carbon_price_per_tco2e: Decimal = Decimal("0")
    domestic_carbon_price_currency: str = "INR"

    # Upstream precursor emissions (for complex goods like steel)
    precursor_emissions: list["CBAMPrecursorEmission"] = field(default_factory=list)


@dataclass
class CBAMPrecursorEmission:
    """Embedded emissions from upstream precursor materials."""
    precursor_name: str
    cn_code: str
    quantity_tonnes: Decimal
    embedded_tco2e_per_tonne: Decimal
    uses_default: bool = True


@dataclass
class CBAMCalculationResult:
    cn_code: str
    goods_description: str
    quantity_tonnes: Decimal

    direct_ee_tco2e: Decimal
    indirect_ee_tco2e: Decimal
    precursor_ee_tco2e: Decimal
    total_ee_tco2e: Decimal
    total_ee_per_tonne: Decimal

    uses_defaults: bool
    default_multiplier: Decimal  # 1.0 for actuals, 3.0 when defaults used

    # Certificate obligation
    cbam_certificates_required: Decimal
    cbam_financial_exposure_eur: Decimal | None

    # Deductions
    domestic_carbon_price_deduction_eur: Decimal

    goods_category: str
    methodology_reference: str


class CBAMCalculator:
    """
    Calculates CBAM embedded emissions per shipment line.
    """

    def __init__(self) -> None:
        self._registry = get_registry()

    def identify_category(self, cn_code: str) -> str | None:
        """Return the CBAM goods category for a CN code, or None if not CBAM goods."""
        cn_clean = cn_code.replace(" ", "").replace(".", "")
        for category, meta in CBAM_GOODS_CATEGORIES.items():
            for prefix in meta["cn_prefixes"]:
                if cn_clean.startswith(prefix):
                    return category
        return None

    def calculate_line(
        self,
        line: CBAMGoodsLine,
        as_of: date,
        cbam_certificate_price_eur: Decimal | None = None,
    ) -> CBAMCalculationResult:
        category = self.identify_category(line.cn_code)
        if category is None:
            raise ValueError(f"CN code {line.cn_code} is not subject to CBAM")

        meta = CBAM_GOODS_CATEGORIES[category]

        # ── Direct Embedded Emissions ─────────────────────────────────────────
        if line.direct_emissions_tco2e_per_tonne is not None and not line.uses_default_direct:
            direct_ee_per_tonne = line.direct_emissions_tco2e_per_tonne
            uses_defaults = False
        else:
            # Use CBAM default value
            factor = self._get_cbam_default(category, line.cn_code, as_of)
            direct_ee_per_tonne = factor.value
            line.uses_default_direct = True
            uses_defaults = True

        direct_ee_tco2e = (direct_ee_per_tonne * line.quantity_tonnes).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )

        # ── Indirect Embedded Emissions (electricity) ─────────────────────────
        indirect_ee_tco2e = Decimal("0")
        if meta["includes_indirect"]:
            if (
                line.electricity_kwh_per_tonne is not None
                and line.grid_emission_factor_tco2e_per_kwh is not None
                and not line.uses_default_indirect
            ):
                indirect_per_tonne = (
                    line.electricity_kwh_per_tonne * line.grid_emission_factor_tco2e_per_kwh
                )
                uses_defaults = False
            else:
                indirect_per_tonne = self._get_cbam_indirect_default(as_of)
                line.uses_default_indirect = True
                uses_defaults = uses_defaults or True

            indirect_ee_tco2e = (indirect_per_tonne * line.quantity_tonnes).quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_UP
            )

        # ── Precursor Embedded Emissions ──────────────────────────────────────
        precursor_ee_tco2e = sum(
            (p.embedded_tco2e_per_tonne * p.quantity_tonnes)
            for p in line.precursor_emissions
        )
        if not precursor_ee_tco2e:
            precursor_ee_tco2e = Decimal("0")

        total_ee_tco2e = direct_ee_tco2e + indirect_ee_tco2e + Decimal(str(precursor_ee_tco2e))
        total_ee_per_tonne = (total_ee_tco2e / line.quantity_tonnes).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        ) if line.quantity_tonnes > 0 else Decimal("0")

        # ── CBAM Certificate Obligation ───────────────────────────────────────
        # Art. 9(2): defaults trigger 3x multiplier
        default_multiplier = Decimal("3") if uses_defaults else Decimal("1")
        cbam_certificates_required = (total_ee_tco2e * default_multiplier).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )

        # Financial exposure
        cbam_financial_exposure_eur = None
        if cbam_certificate_price_eur:
            cbam_financial_exposure_eur = (
                cbam_certificates_required * cbam_certificate_price_eur
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # ── Domestic Carbon Price Deduction (Art. 9) ─────────────────────────
        # Simplified: assume INR to EUR conversion is handled by caller
        domestic_carbon_price_deduction_eur = Decimal("0")
        if line.domestic_carbon_price_per_tco2e > 0:
            # Caller must provide EUR-converted price
            domestic_carbon_price_deduction_eur = (
                line.domestic_carbon_price_per_tco2e * total_ee_tco2e
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return CBAMCalculationResult(
            cn_code=line.cn_code,
            goods_description=line.goods_description,
            quantity_tonnes=line.quantity_tonnes,
            direct_ee_tco2e=direct_ee_tco2e,
            indirect_ee_tco2e=indirect_ee_tco2e,
            precursor_ee_tco2e=Decimal(str(precursor_ee_tco2e)),
            total_ee_tco2e=total_ee_tco2e,
            total_ee_per_tonne=total_ee_per_tonne,
            uses_defaults=uses_defaults,
            default_multiplier=default_multiplier,
            cbam_certificates_required=cbam_certificates_required,
            cbam_financial_exposure_eur=cbam_financial_exposure_eur,
            domestic_carbon_price_deduction_eur=domestic_carbon_price_deduction_eur,
            goods_category=category,
            methodology_reference=meta["methodology"],
        )

    def _get_cbam_default(self, category: str, cn_code: str, as_of: date):
        """Resolve CBAM default emission factor for a goods category."""
        try:
            return self._registry.get(
                activity_type="process_emissions",
                as_of=as_of,
                fuel_type=self._category_fuel_key(category, cn_code),
                source_preference=[FactorSource.EU_CBAM_DEFAULT],
            )
        except KeyError:
            raise ValueError(
                f"No CBAM default factor found for category={category}, cn_code={cn_code}. "
                "Please update the cbam_defaults.yaml factor library."
            )

    def _get_cbam_indirect_default(self, as_of: date):
        """World average grid factor used when indirect defaults apply."""
        return self._registry.get(
            activity_type="purchased_electricity",
            as_of=as_of,
            fuel_type="electricity_cbam",
            source_preference=[FactorSource.EU_CBAM_DEFAULT],
        )

    def _category_fuel_key(self, category: str, cn_code: str) -> str:
        """Map CN code to the fuel_type key used in cbam_defaults.yaml."""
        prefix = cn_code[:4]
        mapping = {
            "7206": "crude_steel_bof",
            "7207": "crude_steel_bof",
            "7208": "crude_steel_bof",
            "7213": "crude_steel_eaf",
            "7214": "crude_steel_eaf",
            "2523": "portland_cement",
            "7601": "primary_aluminium",
            "7602": "secondary_aluminium",
            "2808": "nitric_acid",
            "2814": "ammonia",
            "3102": "urea",
            "2804": "hydrogen",
            "2716": "electricity_cbam",
        }
        return mapping.get(prefix, f"{category}_default")
