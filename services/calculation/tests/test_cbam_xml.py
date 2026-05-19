"""
Tests for the CBAM XML generator.
Validates output structure, hash consistency, and decimal precision.
"""
import pytest
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal

from services.reporting.app.generators.cbam_xml import (
    CBAMQuarterlyReport, CBAMGoodsEmission, CBAMInstallation,
    generate_cbam_xml, CBAM_NS, CBAM_COMMON_NS
)


@pytest.fixture
def sample_installation():
    return CBAMInstallation(
        installation_name="Tirupur Textile Mills Ltd",
        installation_address="SIPCOT Industrial Complex, Tirupur 641604",
        country_code="IN",
        operator_name="Tirupur Textile Mills Ltd",
    )


@pytest.fixture
def sample_goods_line(sample_installation):
    return CBAMGoodsEmission(
        cn_code="7208100000",
        goods_description="Flat-rolled products of iron or non-alloy steel",
        quantity_net_mass_tonnes=Decimal("250.500"),
        direct_embedded_tco2e=Decimal("511.271"),   # 250.5t × 2.0418 tCO2e/t
        indirect_embedded_tco2e=Decimal("0"),        # EAF — indirect captured elsewhere
        direct_embedded_per_tonne=Decimal("2.0418"),
        indirect_embedded_per_tonne=Decimal("0"),
        uses_default_values=True,
        methodology="Annex III Section 4",
        installation=sample_installation,
    )


@pytest.fixture
def sample_report(sample_goods_line):
    return CBAMQuarterlyReport(
        declarant_id="IN-CBAM-2024-001234",
        declarant_name="Auto-Components India Exports Pvt Ltd",
        declarant_address="Plot 42, Pimpri Industrial Area, Pune 411018",
        declarant_eori=None,
        quarter_year=2024,
        quarter_number=1,
        reporting_date=date(2024, 4, 30),
        goods_lines=[sample_goods_line],
    )


class TestCBAMXMLGeneration:
    def test_generates_valid_xml(self, sample_report):
        xml_str, report_hash = generate_cbam_xml(sample_report)
        assert xml_str is not None
        assert len(xml_str) > 100
        # Must parse without errors
        root = ET.fromstring(xml_str)
        assert root is not None

    def test_report_hash_is_sha256(self, sample_report):
        _, report_hash = generate_cbam_xml(sample_report)
        assert len(report_hash) == 64
        assert all(c in "0123456789abcdef" for c in report_hash)

    def test_hash_deterministic(self, sample_report):
        _, hash1 = generate_cbam_xml(sample_report)
        _, hash2 = generate_cbam_xml(sample_report)
        assert hash1 == hash2

    def test_contains_declarant_id(self, sample_report):
        xml_str, _ = generate_cbam_xml(sample_report)
        root = ET.fromstring(xml_str)
        declarant_id_el = root.find(f".//{{{CBAM_COMMON_NS}}}DeclarantID")
        assert declarant_id_el is not None
        assert declarant_id_el.text == "IN-CBAM-2024-001234"

    def test_contains_goods_line(self, sample_report):
        xml_str, _ = generate_cbam_xml(sample_report)
        root = ET.fromstring(xml_str)
        import_lines = root.findall(f".//{{{CBAM_NS}}}ImportLine")
        assert len(import_lines) == 1

    def test_cn_code_in_output(self, sample_report):
        xml_str, _ = generate_cbam_xml(sample_report)
        root = ET.fromstring(xml_str)
        cn = root.find(f".//{{{CBAM_COMMON_NS}}}CNCode")
        assert cn is not None
        assert cn.text == "7208100000"

    def test_defaults_flag_in_output(self, sample_report):
        xml_str, _ = generate_cbam_xml(sample_report)
        root = ET.fromstring(xml_str)
        defaults_el = root.find(f".//{{{CBAM_COMMON_NS}}}UsesDefaultValues")
        assert defaults_el is not None
        assert defaults_el.text == "true"

    def test_period_dates(self, sample_report):
        """Q1 2024 should span 2024-01-01 to 2024-03-31"""
        assert sample_report.period_start == date(2024, 1, 1)
        assert sample_report.period_end == date(2024, 3, 31)

    def test_period_q4(self):
        report = CBAMQuarterlyReport(
            declarant_id="test", declarant_name="test", declarant_address="test",
            declarant_eori=None, quarter_year=2023, quarter_number=4,
            reporting_date=date(2024, 1, 31), goods_lines=[]
        )
        assert report.period_start == date(2023, 10, 1)
        assert report.period_end == date(2023, 12, 31)

    def test_total_tco2e_in_totals(self, sample_report, sample_goods_line):
        xml_str, _ = generate_cbam_xml(sample_report)
        root = ET.fromstring(xml_str)
        total_el = root.find(f".//{{{CBAM_COMMON_NS}}}TotalEmbeddedTCO2e")
        assert total_el is not None
        total = Decimal(total_el.text)
        expected = (sample_goods_line.direct_embedded_tco2e +
                    sample_goods_line.indirect_embedded_tco2e).quantize(Decimal("0.001"))
        assert total == expected

    def test_xml_declaration_present(self, sample_report):
        xml_str, _ = generate_cbam_xml(sample_report)
        assert xml_str.startswith('<?xml version="1.0" encoding="UTF-8"?>')


class TestAuditChain:
    def test_chain_hash_changes_on_modification(self):
        from services.audit.app.ledger import (
            _compute_chain_hash, _compute_payload_hash, AuditEvent
        )
        from uuid import uuid4

        tenant_id = uuid4()
        event = AuditEvent(
            tenant_id=tenant_id,
            event_type="report.generated",
            action="create",
            resource_type="report",
            resource_id="abc123",
        )
        ph = _compute_payload_hash(event)
        ch1 = _compute_chain_hash(ph, None, 1)
        ch2 = _compute_chain_hash(ph, "some_previous_hash", 2)
        assert ch1 != ch2

    def test_payload_hash_deterministic(self):
        from services.audit.app.ledger import _compute_payload_hash, AuditEvent
        from uuid import uuid4
        from datetime import datetime, timezone

        tenant_id = uuid4()
        ts = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        event = AuditEvent(
            tenant_id=tenant_id,
            event_type="data.imported",
            action="create",
        )
        event.created_at = ts  # fix timestamp for determinism
        h1 = _compute_payload_hash(event)
        h2 = _compute_payload_hash(event)
        assert h1 == h2
        assert len(h1) == 64
