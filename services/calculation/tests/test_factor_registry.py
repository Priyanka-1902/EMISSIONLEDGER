"""
Tests for the emission factor registry.
Validates provenance, factor lookup, and version hash integrity.
"""
import pytest
from datetime import date
from decimal import Decimal

from shared.factors.loader import build_default_registry, load_factors_from_yaml
from shared.factors.registry import FactorRegistry
from shared.schemas.factor import FactorSource


@pytest.fixture(scope="module")
def registry():
    return build_default_registry()


class TestFactorRegistry:
    def test_registry_loads_factors(self, registry):
        factors = registry.list_all()
        assert len(factors) > 0

    def test_india_grid_factors_loaded(self, registry):
        factor = registry.get(
            "purchased_electricity",
            as_of=date(2024, 6, 1),
            grid_region="national"
        )
        assert factor is not None
        assert factor.source == FactorSource.CEA_CO2_BASELINE

    def test_national_grid_value_correct(self, registry):
        """CEA 2023-24 national combined margin = 0.7051 kgCO2e/kWh"""
        factor = registry.get(
            "purchased_electricity",
            as_of=date(2024, 1, 1),
            grid_region="national"
        )
        assert factor.value == Decimal("0.7051")
        assert factor.unit == "kgCO2e/kWh"

    def test_tamil_nadu_grid_different_from_national(self, registry):
        tn = registry.get("purchased_electricity", as_of=date(2024, 1, 1), grid_region="tamil_nadu")
        national = registry.get("purchased_electricity", as_of=date(2024, 1, 1), grid_region="national")
        assert tn.value != national.value

    def test_diesel_factor_loaded(self, registry):
        factor = registry.get(
            "stationary_combustion",
            as_of=date(2024, 1, 1),
            fuel_type="diesel"
        )
        assert factor is not None
        assert factor.value > 0
        assert "litre" in factor.unit

    def test_cbam_default_cement_loaded(self, registry):
        factor = registry.get(
            "process_emissions",
            as_of=date(2024, 1, 1),
            fuel_type="portland_cement",
            source_preference=[FactorSource.EU_CBAM_DEFAULT],
        )
        assert factor is not None
        assert factor.source == FactorSource.EU_CBAM_DEFAULT
        assert factor.value == Decimal("0.7677")

    def test_version_hash_present_on_all_factors(self, registry):
        for factor in registry.list_all():
            assert factor.version_hash is not None
            assert len(factor.version_hash) == 64

    def test_version_hash_unique(self, registry):
        hashes = [f.version_hash for f in registry.list_all()]
        assert len(hashes) == len(set(hashes)), "Duplicate version hashes found"

    def test_effective_date_filtering(self, registry):
        """Factor effective from 2023-04-01 should not appear before that date"""
        with pytest.raises(KeyError):
            registry.get(
                "purchased_electricity",
                as_of=date(2022, 12, 31),
                grid_region="national"
            )

    def test_no_factor_for_unknown_activity(self, registry):
        with pytest.raises(KeyError):
            registry.get(
                "antimatter_combustion",
                as_of=date(2024, 1, 1),
            )

    def test_source_publication_present(self, registry):
        """Every factor must have a source publication for auditability"""
        for factor in registry.list_all():
            assert factor.source_publication, f"Factor {factor.id} missing source_publication"
            assert len(factor.source_publication) > 10

    def test_gwp_basis_present(self, registry):
        for factor in registry.list_all():
            assert factor.gwp_basis in ("AR5", "AR6", "AR4")

    def test_factor_by_id_lookup(self, registry):
        all_factors = registry.list_all()
        target = all_factors[0]
        found = registry.get_by_id(target.id)
        assert found.id == target.id

    def test_factor_by_id_not_found(self, registry):
        from uuid import uuid4
        with pytest.raises(KeyError):
            registry.get_by_id(uuid4())
