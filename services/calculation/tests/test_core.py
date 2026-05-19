"""
Unit tests for the GHG calculation engine core.

These tests verify:
1. Correct tCO2e computation for known factor/quantity combinations
2. Confidence interval propagation
3. Input and output hash determinism (audit traceability)
4. Unit normalisation
5. Factor lookup failure handling
"""
import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.engine.core import (
    GHGCalculator, CalculationInput, _normalise_quantity,
    _compute_input_hash, _compute_output_hash, UNCERTAINTY_MAP
)
from shared.schemas.emission import (
    Scope, ActivityType, CalculationMethod, ConfidenceLevel
)
from shared.factors.loader import build_default_registry
from shared.factors.registry import FactorRegistry
from shared.schemas.factor import EmissionFactor, FactorSource, GasType


@pytest.fixture
def registry():
    return build_default_registry()


@pytest.fixture
def calculator(registry):
    calc = GHGCalculator()
    calc._registry = registry
    return calc


def make_input(**kwargs) -> CalculationInput:
    defaults = dict(
        tenant_id=uuid4(),
        facility_id=uuid4(),
        activity_date=date(2024, 1, 15),
        scope=Scope.SCOPE_2,
        activity_type=ActivityType.PURCHASED_ELECTRICITY,
        activity_quantity=Decimal("1000"),
        activity_unit="kWh",
        activity_description="Monthly electricity — Jan 2024",
        source_system="manual",
        grid_region="national",
    )
    defaults.update(kwargs)
    return CalculationInput(**defaults)


# ── Unit normalisation ────────────────────────────────────────────────────────

class TestNormaliseQuantity:
    def test_kwh_passthrough(self):
        qty, unit = _normalise_quantity(Decimal("500"), "kWh")
        assert qty == Decimal("500")
        assert unit == "kWh"

    def test_mwh_to_kwh(self):
        qty, unit = _normalise_quantity(Decimal("2"), "MWh")
        assert qty == Decimal("2000")
        assert unit == "kWh"

    def test_litre_passthrough(self):
        qty, unit = _normalise_quantity(Decimal("100"), "litre")
        assert qty == Decimal("100")
        assert unit == "litre"

    def test_kl_to_litre(self):
        qty, unit = _normalise_quantity(Decimal("5"), "kl")
        assert qty == Decimal("5000")
        assert unit == "litre"

    def test_tonne_to_kg(self):
        qty, unit = _normalise_quantity(Decimal("1"), "tonne")
        assert qty == Decimal("1000")
        assert unit == "kg"

    def test_unknown_unit_raises(self):
        with pytest.raises(ValueError, match="Unknown unit"):
            _normalise_quantity(Decimal("100"), "gallons")


# ── Hash determinism ──────────────────────────────────────────────────────────

class TestHashes:
    def test_input_hash_deterministic(self):
        factor_id = uuid4()
        h1 = _compute_input_hash(Decimal("1000"), factor_id, Decimal("0.7051"))
        h2 = _compute_input_hash(Decimal("1000"), factor_id, Decimal("0.7051"))
        assert h1 == h2
        assert len(h1) == 64

    def test_input_hash_changes_with_quantity(self):
        factor_id = uuid4()
        h1 = _compute_input_hash(Decimal("1000"), factor_id, Decimal("0.7051"))
        h2 = _compute_input_hash(Decimal("1001"), factor_id, Decimal("0.7051"))
        assert h1 != h2

    def test_output_hash_deterministic(self):
        input_hash = "abc123" * 10 + "abcd"
        h1 = _compute_output_hash(Decimal("0.7051"), input_hash)
        h2 = _compute_output_hash(Decimal("0.7051"), input_hash)
        assert h1 == h2

    def test_output_hash_chains_input(self):
        h1 = _compute_output_hash(Decimal("1"), "aaa" * 21 + "aa")
        h2 = _compute_output_hash(Decimal("1"), "bbb" * 21 + "bb")
        assert h1 != h2


# ── Calculation correctness ───────────────────────────────────────────────────

class TestGHGCalculation:
    def test_electricity_scope2_national_grid(self, calculator):
        """
        1000 kWh × 0.7051 kgCO2e/kWh ÷ 1000 = 0.7051 tCO2e
        CEA national grid factor 2023-24
        """
        inp = make_input(
            activity_quantity=Decimal("1000"),
            activity_unit="kWh",
            grid_region="national",
        )
        result, record = calculator.calculate(inp)
        # 1000 kWh × 0.7051 kgCO2e/kWh → 0.7051 tCO2e
        assert result.tco2e == pytest.approx(Decimal("0.705100"), rel=1e-4)
        assert result.tco2e_lower < result.tco2e
        assert result.tco2e_upper > result.tco2e

    def test_electricity_mwh_unit(self, calculator):
        """1 MWh should give same result as 1000 kWh"""
        inp_kwh = make_input(activity_quantity=Decimal("1000"), activity_unit="kWh")
        inp_mwh = make_input(activity_quantity=Decimal("1"), activity_unit="MWh")
        r1, _ = calculator.calculate(inp_kwh)
        r2, _ = calculator.calculate(inp_mwh)
        assert r1.tco2e == r2.tco2e

    def test_tamil_nadu_grid_lower_than_national(self, calculator):
        """Tamil Nadu has a cleaner grid (0.6512) than national (0.7051)"""
        inp_national = make_input(grid_region="national")
        inp_tn = make_input(grid_region="tamil_nadu")
        r_national, _ = calculator.calculate(inp_national)
        r_tn, _ = calculator.calculate(inp_tn)
        assert r_tn.tco2e < r_national.tco2e

    def test_confidence_intervals_high(self, calculator):
        """High confidence: ±5% uncertainty bands"""
        inp = make_input(confidence_level=ConfidenceLevel.HIGH)
        result, _ = calculator.calculate(inp)
        expected_lower = result.tco2e * (1 - Decimal("0.05"))
        expected_upper = result.tco2e * (1 + Decimal("0.05"))
        assert result.tco2e_lower == pytest.approx(expected_lower, rel=1e-4)
        assert result.tco2e_upper == pytest.approx(expected_upper, rel=1e-4)

    def test_confidence_intervals_low(self, calculator):
        """Low confidence (spend-based): ±50% uncertainty bands"""
        inp = make_input(confidence_level=ConfidenceLevel.LOW)
        result, _ = calculator.calculate(inp)
        uncertainty = UNCERTAINTY_MAP[ConfidenceLevel.LOW]
        expected_lower = result.tco2e * (1 - uncertainty)
        assert result.tco2e_lower == pytest.approx(expected_lower, rel=1e-4)

    def test_audit_hashes_present(self, calculator):
        inp = make_input()
        result, record = calculator.calculate(inp)
        assert result.input_hash is not None
        assert len(result.input_hash) == 64
        assert result.output_hash is not None
        assert len(result.output_hash) == 64

    def test_factor_version_hash_on_record(self, calculator):
        inp = make_input()
        _, record = calculator.calculate(inp)
        assert record.factor_version_hash is not None
        assert len(record.factor_version_hash) == 64

    def test_record_scope_matches_input(self, calculator):
        inp = make_input(scope=Scope.SCOPE_2)
        _, record = calculator.calculate(inp)
        assert record.scope == Scope.SCOPE_2

    def test_unknown_grid_region_raises(self, calculator):
        inp = make_input(grid_region="mars")
        with pytest.raises(KeyError):
            calculator.calculate(inp)

    def test_zero_quantity_not_accepted(self):
        """Pydantic should reject zero quantity at the API layer (tested here for defence)"""
        with pytest.raises(Exception):
            CalculationInput(
                tenant_id=uuid4(),
                facility_id=uuid4(),
                activity_date=date(2024, 1, 1),
                scope=Scope.SCOPE_2,
                activity_type=ActivityType.PURCHASED_ELECTRICITY,
                activity_quantity=Decimal("0"),  # invalid
                activity_unit="kWh",
                activity_description="test",
                source_system="manual",
            )

    def test_batch_calculation(self, calculator):
        inputs = [make_input(activity_quantity=Decimal(str(q))) for q in [100, 500, 1000]]
        results = calculator.calculate_batch(inputs)
        assert len(results) == 3
        # tCO2e should scale linearly
        r0, r1, r2 = [r[0].tco2e for r in results]
        assert r1 == pytest.approx(r0 * 5, rel=1e-4)
        assert r2 == pytest.approx(r0 * 10, rel=1e-4)


# ── CBAM calculator ───────────────────────────────────────────────────────────

class TestCBAMCalculator:
    def test_cbam_category_identification(self):
        from app.engine.cbam import CBAMCalculator
        calc = CBAMCalculator()
        assert calc.identify_category("72081000") == "iron_and_steel"
        assert calc.identify_category("2523210000") == "cement"
        assert calc.identify_category("7601100000") == "aluminium"
        assert calc.identify_category("2814100000") == "fertilisers"
        assert calc.identify_category("2804100000") == "hydrogen"
        assert calc.identify_category("2716000000") == "electricity"
        assert calc.identify_category("0101000000") is None

    def test_cbam_default_multiplier(self):
        from app.engine.cbam import CBAMCalculator, CBAMGoodsLine
        calc = CBAMCalculator()
        line = CBAMGoodsLine(
            cn_code="2523210000",
            goods_description="Portland Cement",
            quantity_tonnes=Decimal("100"),
            country_of_origin="IN",
            uses_default_direct=True,
        )
        result = calc.calculate_line(line, as_of=date(2024, 1, 1))
        assert result.uses_defaults is True
        assert result.default_multiplier == Decimal("3")
        assert result.cbam_certificates_required == result.total_ee_tco2e * Decimal("3")

    def test_cbam_actuals_no_multiplier(self):
        from app.engine.cbam import CBAMCalculator, CBAMGoodsLine
        calc = CBAMCalculator()
        line = CBAMGoodsLine(
            cn_code="2523210000",
            goods_description="Portland Cement",
            quantity_tonnes=Decimal("100"),
            country_of_origin="IN",
            direct_emissions_tco2e_per_tonne=Decimal("0.65"),  # supplier actual
            uses_default_direct=False,
        )
        result = calc.calculate_line(line, as_of=date(2024, 1, 1))
        assert result.uses_defaults is False
        assert result.default_multiplier == Decimal("1")

    def test_cbam_financial_exposure(self):
        from app.engine.cbam import CBAMCalculator, CBAMGoodsLine
        calc = CBAMCalculator()
        line = CBAMGoodsLine(
            cn_code="2523210000",
            goods_description="Portland Cement",
            quantity_tonnes=Decimal("100"),
            country_of_origin="IN",
            uses_default_direct=True,
        )
        cert_price = Decimal("65.00")
        result = calc.calculate_line(line, as_of=date(2024, 1, 1),
                                      cbam_certificate_price_eur=cert_price)
        assert result.cbam_financial_exposure_eur is not None
        expected = result.cbam_certificates_required * cert_price
        assert result.cbam_financial_exposure_eur == pytest.approx(
            expected.quantize(Decimal("0.01")), rel=1e-4
        )
