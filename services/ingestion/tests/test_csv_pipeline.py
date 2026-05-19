"""Tests for the CSV/Excel ingestion pipeline."""
import pytest
from decimal import Decimal
from app.adapters.csv_pipeline import CSVPipeline, CSVParseResult

VALID_FUEL_CSV = b"""date,facility_name,fuel_type,quantity,unit,vendor_name,invoice_number
2024-01-15,Plant A,diesel,500,litre,Bharat Petroleum,INV-001
2024-01-20,Plant B,electricity,1200,kWh,,BESCOM-JAN24
2024-02-01,Plant A,png,200,scm,GAIL,INV-045
"""

INVALID_FUEL_CSV = b"""date,facility_name,fuel_type,quantity,unit
not-a-date,Plant A,diesel,500,litre
2024-01-15,,diesel,500,litre
2024-01-15,Plant A,antimatter,500,litre
2024-01-15,Plant A,diesel,zero,litre
2024-01-15,Plant A,diesel,-5,litre
"""

ELEC_CSV = b"""month,facility_name,units_kwh,discom,bill_number
2024-01,Tirupur Unit 1,45000,TNEB,TNEB-JAN-24-001
2024-02,Tirupur Unit 1,48000,TNEB,TNEB-FEB-24-001
"""


class TestCSVPipeline:
    def test_detects_fuel_template(self):
        pipeline = CSVPipeline(tenant_id="test-tenant")
        headers = ["date", "facility_name", "fuel_type", "quantity", "unit"]
        assert pipeline.detect_template_type(headers) == "fuel_consumption"

    def test_detects_electricity_template(self):
        pipeline = CSVPipeline(tenant_id="test-tenant")
        assert pipeline.detect_template_type(["month", "facility_name", "units_kwh", "discom"]) == "electricity"

    def test_parses_valid_fuel_csv(self):
        pipeline = CSVPipeline(tenant_id="test-tenant")
        result = pipeline.parse_csv(VALID_FUEL_CSV)
        assert result.valid_rows == 3
        assert len(result.errors) == 0
        assert result.template_type == "fuel_consumption"

    def test_fuel_type_normalised(self):
        pipeline = CSVPipeline(tenant_id="test-tenant")
        result = pipeline.parse_csv(VALID_FUEL_CSV)
        fuel_types = {r["fuel_type"] for r in result.records}
        assert "diesel" in fuel_types
        assert "electricity" in fuel_types
        assert "png" in fuel_types

    def test_invalid_date_produces_error(self):
        pipeline = CSVPipeline(tenant_id="test-tenant")
        result = pipeline.parse_csv(INVALID_FUEL_CSV)
        error_cols = [e.column for e in result.errors]
        assert "date" in error_cols

    def test_missing_facility_produces_error(self):
        pipeline = CSVPipeline(tenant_id="test-tenant")
        result = pipeline.parse_csv(INVALID_FUEL_CSV)
        error_cols = [e.column for e in result.errors]
        assert "facility_name" in error_cols

    def test_unknown_fuel_type_produces_error(self):
        pipeline = CSVPipeline(tenant_id="test-tenant")
        result = pipeline.parse_csv(INVALID_FUEL_CSV)
        fuel_errors = [e for e in result.errors if e.column == "fuel_type"]
        assert len(fuel_errors) > 0
        assert any("antimatter" in e.value for e in fuel_errors)

    def test_non_numeric_quantity_produces_error(self):
        pipeline = CSVPipeline(tenant_id="test-tenant")
        result = pipeline.parse_csv(INVALID_FUEL_CSV)
        qty_errors = [e for e in result.errors if e.column == "quantity"]
        assert any("zero" in str(e.value) for e in qty_errors)

    def test_electricity_csv(self):
        pipeline = CSVPipeline(tenant_id="test-tenant")
        result = pipeline.parse_csv(ELEC_CSV)
        assert result.template_type == "electricity"
        assert result.valid_rows == 2
        kwh_values = [r["activity_quantity"] for r in result.records]
        assert Decimal("45000") in kwh_values

    def test_deduplication(self):
        pipeline = CSVPipeline(tenant_id="test-tenant")
        # Parse same file twice — second should be all duplicates
        r1 = pipeline.parse_csv(VALID_FUEL_CSV)
        r2 = pipeline.parse_csv(VALID_FUEL_CSV)
        assert r1.duplicate_count == 0
        assert r2.duplicate_count == r1.valid_rows

    def test_bom_handling(self):
        """Handle UTF-8 BOM from Excel exports"""
        bom_csv = b"\xef\xbb\xbf" + ELEC_CSV
        pipeline = CSVPipeline(tenant_id="test-tenant")
        result = pipeline.parse_csv(bom_csv)
        assert result.valid_rows > 0

    def test_comma_in_quantity_stripped(self):
        csv = b"date,facility_name,fuel_type,quantity,unit\n2024-01-01,Plant A,diesel,\"1,500\",litre\n"
        pipeline = CSVPipeline(tenant_id="test-tenant")
        result = pipeline.parse_csv(csv)
        assert result.valid_rows == 1
        assert result.records[0]["quantity"] == Decimal("1500")
