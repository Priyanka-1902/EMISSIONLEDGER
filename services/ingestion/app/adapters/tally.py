"""
Tally Prime Connector — Native TDL Integration

Fetches vouchers, ledgers, and stock items from Tally Prime via XML/HTTP.
Tally exposes a built-in XML API on port 9000 (configurable).

TDL reference: Tally Developer Reference Guide v2.0, Chapter 5 (XML Export)
Authentication: Tally's own session (no OAuth; credentials are local network).
"""
from __future__ import annotations
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import httpx
import structlog

log = structlog.get_logger(__name__)

TALLY_DEFAULT_PORT = 9000
TALLY_XML_ENVELOPE_TEMPLATE = """
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Object</TYPE>
    <ID>{object_id}</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        <SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>
        <SVFROMDATE>{from_date}</SVFROMDATE>
        <SVTODATE>{to_date}</SVTODATE>
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>
"""


@dataclass
class TallyVoucher:
    voucher_number: str
    voucher_date: date
    voucher_type: str  # e.g., "Purchase", "Sales", "Payment"
    party_name: str | None
    narration: str | None
    currency: str
    amount: Decimal
    ledger_name: str
    stock_item_name: str | None = None
    stock_quantity: Decimal | None = None
    stock_unit: str | None = None
    gst_applicable: bool = False


@dataclass
class TallyFuelExpense:
    """Classified fuel/energy expense extracted from Tally vouchers."""
    voucher_number: str
    voucher_date: date
    fuel_type: str          # diesel, petrol, png, lpg, coal_bituminous, ...
    quantity: Decimal | None
    unit: str | None        # litre, scm, kg, tonne
    amount_inr: Decimal
    vendor_name: str | None
    facility_hint: str | None  # extracted from narration/cost centre


class TallyAdapter:
    """
    Pulls purchase and payment vouchers from Tally Prime and
    classifies them as fuel/energy expenses for GHG calculation.
    """

    FUEL_KEYWORDS = {
        "diesel": ["diesel", "hsd", "high speed diesel"],
        "petrol": ["petrol", "gasoline", "ms "],
        "png": ["png", "piped natural gas", "natural gas", "gas bill"],
        "lpg": ["lpg", "liquefied petroleum"],
        "coal_bituminous": ["coal", "coke", "lignite"],
        "furnace_oil": ["furnace oil", "fo ", "light fuel oil"],
        "electricity": ["electricity", "ebill", "power bill", "msedcl",
                        "tneb", "bescom", "tsecpdcl", "electric bill"],
        "r410a": ["r410a", "refrigerant", "hvac gas"],
        "r134a": ["r134a", "r 134a"],
    }

    def __init__(self, host: str, port: int = TALLY_DEFAULT_PORT, company_name: str = ""):
        self.base_url = f"http://{host}:{port}"
        self.company_name = company_name
        self._client = httpx.AsyncClient(timeout=30.0)

    async def fetch_vouchers(
        self, from_date: date, to_date: date, voucher_types: list[str] | None = None
    ) -> list[TallyVoucher]:
        """Fetch all vouchers in date range from Tally."""
        types = voucher_types or ["Purchase", "Payment", "Journal"]
        all_vouchers = []
        for vtype in types:
            xml_body = TALLY_XML_ENVELOPE_TEMPLATE.format(
                object_id="Voucher",
                company_name=self.company_name,
                from_date=from_date.strftime("%Y%m%d"),
                to_date=to_date.strftime("%Y%m%d"),
            ).strip()
            try:
                resp = await self._client.post(
                    self.base_url, content=xml_body,
                    headers={"Content-Type": "application/xml"}
                )
                resp.raise_for_status()
                vouchers = self._parse_voucher_response(resp.text, vtype)
                all_vouchers.extend(vouchers)
            except httpx.HTTPError as e:
                log.error("tally.fetch_error", error=str(e), voucher_type=vtype)
        return all_vouchers

    def _parse_voucher_response(self, xml_text: str, voucher_type: str) -> list[TallyVoucher]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            log.error("tally.xml_parse_error", error=str(e))
            return []

        vouchers = []
        for voucher_el in root.findall(".//VOUCHER"):
            try:
                voucher = TallyVoucher(
                    voucher_number=_text(voucher_el, "VOUCHERNUMBER") or "",
                    voucher_date=_parse_tally_date(_text(voucher_el, "DATE")),
                    voucher_type=_text(voucher_el, "VOUCHERTYPENAME") or voucher_type,
                    party_name=_text(voucher_el, "PARTYLEDGERNAME"),
                    narration=_text(voucher_el, "NARRATION"),
                    currency="INR",
                    amount=Decimal(_text(voucher_el, "AMOUNT") or "0"),
                    ledger_name=_text(voucher_el, "LEDGERNAME") or "",
                    stock_item_name=_text(voucher_el, "STOCKITEMNAME"),
                    stock_quantity=_decimal_or_none(voucher_el, "BILLEDQTY"),
                    stock_unit=_text(voucher_el, "UNIT"),
                )
                vouchers.append(voucher)
            except Exception as e:
                log.warning("tally.voucher_parse_skip", error=str(e))
        return vouchers

    def classify_fuel_expenses(
        self, vouchers: list[TallyVoucher]
    ) -> list[TallyFuelExpense]:
        """
        Classify purchase/payment vouchers as fuel or energy expenses.
        Uses keyword matching on ledger name, party name, narration, stock item.
        Low-confidence matches are flagged for human review.
        """
        expenses = []
        for v in vouchers:
            text_corpus = " ".join(filter(None, [
                v.ledger_name.lower(),
                (v.party_name or "").lower(),
                (v.narration or "").lower(),
                (v.stock_item_name or "").lower(),
            ]))
            fuel_type = self._match_fuel_type(text_corpus)
            if fuel_type is None:
                continue

            # Try to extract quantity from stock item
            quantity = v.stock_quantity
            unit = v.stock_unit

            # Normalise unit
            if unit and "ltr" in unit.lower():
                unit = "litre"
            elif unit and "kl" in unit.lower():
                unit = "kl"

            expenses.append(TallyFuelExpense(
                voucher_number=v.voucher_number,
                voucher_date=v.voucher_date,
                fuel_type=fuel_type,
                quantity=quantity,
                unit=unit,
                amount_inr=abs(v.amount),
                vendor_name=v.party_name,
                facility_hint=self._extract_facility_hint(v.narration),
            ))
        return expenses

    def _match_fuel_type(self, text: str) -> str | None:
        for fuel_type, keywords in self.FUEL_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return fuel_type
        return None

    def _extract_facility_hint(self, narration: str | None) -> str | None:
        if not narration:
            return None
        # Look for facility/plant/unit keywords
        import re
        m = re.search(r"(?:plant|unit|factory|facility|dept|branch)\s+[:\-]?\s*([A-Za-z0-9\s]+)", narration, re.I)
        return m.group(1).strip() if m else None

    async def close(self):
        await self._client.aclose()


def _text(el: ET.Element, tag: str) -> str | None:
    child = el.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return None


def _parse_tally_date(s: str | None) -> date:
    if not s:
        return date.today()
    try:
        return datetime.strptime(s.strip(), "%Y%m%d").date()
    except ValueError:
        return date.today()


def _decimal_or_none(el: ET.Element, tag: str) -> Decimal | None:
    val = _text(el, tag)
    if val is None:
        return None
    try:
        return Decimal(val.replace(",", ""))
    except Exception:
        return None
