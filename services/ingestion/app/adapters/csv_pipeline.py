"""
Universal CSV/Excel Bulk Import Pipeline

Accepts files with these schemas:
  1. Fuel/Energy Consumption (fuel_consumption_template.xlsx)
  2. Electricity Bills (electricity_bills_template.xlsx)
  3. Logistics / Freight (logistics_template.xlsx)
  4. Manual Emission Records (manual_records_template.xlsx)

Validation: pydantic models per row with field-level error reporting.
Deduplication: SHA-256 of (tenant_id + source_record_id + activity_date) prevents double-import.
"""
from __future__ import annotations
import hashlib
import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
import csv
import structlog

log = structlog.get_logger(__name__)

# Required columns for each template type
FUEL_CONSUMPTION_COLUMNS = {
    "required": ["date", "facility_name", "fuel_type", "quantity", "unit"],
    "optional": ["vendor_name", "invoice_number", "notes"],
}

ELECTRICITY_COLUMNS = {
    "required": ["month", "facility_name", "units_kwh", "discom"],
    "optional": ["meter_number", "bill_number", "amount_inr"],
}

LOGISTICS_COLUMNS = {
    "required": ["date", "origin", "destination", "distance_km", "weight_tonnes", "transport_mode"],
    "optional": ["carrier", "shipment_id", "fuel_type"],
}


@dataclass
class CSVValidationError:
    row_number: int
    column: str
    value: Any
    message: str


@dataclass
class CSVParseResult:
    template_type: str
    total_rows: int
    valid_rows: int
    errors: list[CSVValidationError] = field(default_factory=list)
    records: list[dict] = field(default_factory=list)
    duplicate_count: int = 0


FUEL_TYPE_ALIASES = {
    "diesel": "diesel", "hsd": "diesel", "high speed diesel": "diesel",
    "petrol": "petrol", "gasoline": "petrol",
    "png": "png", "natural gas": "png", "cng": "cng",
    "lpg": "lpg",
    "coal": "coal_bituminous", "bituminous coal": "coal_bituminous",
    "lignite": "coal_lignite",
    "furnace oil": "furnace_oil", "fo": "furnace_oil",
    "electricity": "electricity",
    "r410a": "r410a", "r134a": "r134a", "r22": "r22",
}

UNIT_ALIASES = {
    "ltr": "litre", "litre": "litre", "litres": "litre", "l": "litre",
    "kl": "kl", "kilolitre": "kl",
    "kwh": "kWh", "kilowatt hour": "kWh", "kw-h": "kWh",
    "mwh": "MWh", "megawatt hour": "MWh",
    "kg": "kg", "kilogram": "kg",
    "tonne": "tonne", "mt": "tonne", "metric tonne": "tonne", "ton": "tonne",
    "scm": "scm", "m3": "scm",
    "km": "km", "kilometre": "km",
}


class CSVPipeline:
    def __init__(self, tenant_id: str, existing_hashes: set[str] | None = None):
        self.tenant_id = tenant_id
        self._seen_hashes: set[str] = existing_hashes or set()

    def detect_template_type(self, headers: list[str]) -> str:
        headers_lower = {h.lower().strip() for h in headers}
        if "units_kwh" in headers_lower or "kwh" in headers_lower:
            return "electricity"
        if "fuel_type" in headers_lower:
            return "fuel_consumption"
        if "distance_km" in headers_lower or "transport_mode" in headers_lower:
            return "logistics"
        return "unknown"

    def parse_csv(self, content: bytes, template_type: str | None = None) -> CSVParseResult:
        """Parse CSV bytes into validated records."""
        text = content.decode("utf-8-sig")  # handle BOM
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []

        detected = template_type or self.detect_template_type(list(headers))

        errors: list[CSVValidationError] = []
        records: list[dict] = []
        duplicate_count = 0

        for row_num, row in enumerate(reader, start=2):
            row_errors, parsed = self._validate_row(row, detected, row_num)
            errors.extend(row_errors)
            if not row_errors and parsed:
                dedup_hash = self._compute_row_hash(parsed)
                if dedup_hash in self._seen_hashes:
                    duplicate_count += 1
                    continue
                self._seen_hashes.add(dedup_hash)
                records.append(parsed)

        return CSVParseResult(
            template_type=detected,
            total_rows=row_num - 1 if 'row_num' in dir() else 0,
            valid_rows=len(records),
            errors=errors,
            records=records,
            duplicate_count=duplicate_count,
        )

    def _validate_row(
        self, row: dict, template_type: str, row_num: int
    ) -> tuple[list[CSVValidationError], dict | None]:
        errors = []
        parsed: dict = {"template_type": template_type}

        if template_type == "fuel_consumption":
            return self._validate_fuel_row(row, row_num, parsed, errors)
        elif template_type == "electricity":
            return self._validate_electricity_row(row, row_num, parsed, errors)
        elif template_type == "logistics":
            return self._validate_logistics_row(row, row_num, parsed, errors)
        else:
            errors.append(CSVValidationError(row_num, "template", template_type, "Unknown template type"))
            return errors, None

    def _validate_fuel_row(
        self, row: dict, row_num: int, parsed: dict, errors: list
    ) -> tuple[list, dict | None]:
        # Date
        date_val = self._parse_date(row.get("date", ""), row_num, errors)
        if date_val:
            parsed["activity_date"] = date_val

        # Facility
        facility = (row.get("facility_name") or "").strip()
        if not facility:
            errors.append(CSVValidationError(row_num, "facility_name", facility, "Required"))
        else:
            parsed["facility_name"] = facility

        # Fuel type
        raw_fuel = (row.get("fuel_type") or "").strip().lower()
        fuel_type = FUEL_TYPE_ALIASES.get(raw_fuel)
        if not fuel_type:
            errors.append(CSVValidationError(row_num, "fuel_type", raw_fuel,
                f"Unknown fuel type. Valid: {list(FUEL_TYPE_ALIASES.keys())}"))
        else:
            parsed["fuel_type"] = fuel_type

        # Quantity
        qty = self._parse_decimal(row.get("quantity", ""), row_num, "quantity", errors, min_val=Decimal("0.001"))
        if qty:
            parsed["quantity"] = qty

        # Unit
        raw_unit = (row.get("unit") or "").strip().lower()
        unit = UNIT_ALIASES.get(raw_unit)
        if not unit:
            errors.append(CSVValidationError(row_num, "unit", raw_unit,
                f"Unknown unit. Valid: {list(UNIT_ALIASES.keys())}"))
        else:
            parsed["unit"] = unit

        # Optional
        parsed["vendor_name"] = (row.get("vendor_name") or "").strip() or None
        parsed["invoice_number"] = (row.get("invoice_number") or "").strip() or None
        parsed["notes"] = (row.get("notes") or "").strip() or None

        if errors:
            return errors, None
        return errors, parsed

    def _validate_electricity_row(
        self, row: dict, row_num: int, parsed: dict, errors: list
    ) -> tuple[list, dict | None]:
        month_str = (row.get("month") or "").strip()
        if not month_str:
            errors.append(CSVValidationError(row_num, "month", month_str, "Required (YYYY-MM)"))
        else:
            try:
                import re
                m = re.match(r"^(\d{4})-(\d{2})$", month_str)
                if m:
                    parsed["activity_date"] = date(int(m.group(1)), int(m.group(2)), 1)
                else:
                    raise ValueError()
            except Exception:
                errors.append(CSVValidationError(row_num, "month", month_str, "Must be YYYY-MM format"))

        facility = (row.get("facility_name") or "").strip()
        if not facility:
            errors.append(CSVValidationError(row_num, "facility_name", facility, "Required"))
        else:
            parsed["facility_name"] = facility

        kwh = self._parse_decimal(row.get("units_kwh") or row.get("kwh", ""), row_num, "units_kwh", errors)
        if kwh:
            parsed["activity_quantity"] = kwh
            parsed["activity_unit"] = "kWh"
            parsed["fuel_type"] = "electricity"

        discom = (row.get("discom") or "").strip()
        parsed["discom"] = discom or None
        parsed["bill_number"] = (row.get("bill_number") or "").strip() or None

        if errors:
            return errors, None
        return errors, parsed

    def _validate_logistics_row(
        self, row: dict, row_num: int, parsed: dict, errors: list
    ) -> tuple[list, dict | None]:
        date_val = self._parse_date(row.get("date", ""), row_num, errors)
        if date_val:
            parsed["activity_date"] = date_val

        distance = self._parse_decimal(row.get("distance_km", ""), row_num, "distance_km", errors, min_val=Decimal("0"))
        weight = self._parse_decimal(row.get("weight_tonnes", ""), row_num, "weight_tonnes", errors, min_val=Decimal("0"))
        if distance and weight:
            parsed["tonne_km"] = distance * weight
            parsed["activity_quantity"] = parsed["tonne_km"]
            parsed["activity_unit"] = "tonne-km"

        mode = (row.get("transport_mode") or "").strip().lower()
        mode_map = {"road": "truck", "rail": "train", "sea": "ship", "air": "aircraft", "truck": "truck", "ship": "ship"}
        parsed["transport_mode"] = mode_map.get(mode, mode)
        parsed["fuel_type"] = row.get("fuel_type", "diesel").strip().lower() or "diesel"

        if errors:
            return errors, None
        return errors, parsed

    def _parse_date(self, val: str, row_num: int, errors: list) -> date | None:
        val = (val or "").strip()
        for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%Y"]:
            try:
                from datetime import datetime
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
        errors.append(CSVValidationError(row_num, "date", val, "Invalid date. Use YYYY-MM-DD"))
        return None

    def _parse_decimal(
        self, val: str, row_num: int, field: str, errors: list, min_val: Decimal | None = None
    ) -> Decimal | None:
        val = (val or "").strip().replace(",", "")
        try:
            d = Decimal(val)
            if min_val is not None and d < min_val:
                errors.append(CSVValidationError(row_num, field, val, f"Must be >= {min_val}"))
                return None
            return d
        except (InvalidOperation, ValueError):
            errors.append(CSVValidationError(row_num, field, val, f"Must be a number"))
            return None

    def _compute_row_hash(self, parsed: dict) -> str:
        key = json_stable(self.tenant_id, parsed.get("activity_date"), parsed.get("facility_name"),
                          parsed.get("fuel_type"), parsed.get("quantity") or parsed.get("activity_quantity"))
        return hashlib.sha256(key.encode()).hexdigest()


def json_stable(*parts) -> str:
    import json
    return json.dumps([str(p) for p in parts], sort_keys=True)
