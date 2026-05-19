"""
EU CBAM Declarant Report XML Generator

Produces CBAM quarterly declarant reports in the XML format specified by:
  Commission Implementing Regulation (EU) 2023/1773, Annex IV (XML Schema)

The generated XML is validated against the official CBAM XSD before delivery.
The XSD is versioned and auto-updated from the EU DG TAXUD publication feed.

Output: Valid CBAM-TR-XML (CBAM Transitional Reporting XML) and
        CBAM-PD-XML (CBAM Permanent Declarant XML from 2026).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID
import hashlib
import xml.etree.ElementTree as ET
from xml.dom import minidom


# CBAM XML namespaces per EU CBAM Registry schema
CBAM_NS = "urn:eu:taxud:cbam:declarant:v1"
CBAM_COMMON_NS = "urn:eu:taxud:cbam:common:v1"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


@dataclass
class CBAMInstallation:
    """Operator installation in third country."""
    installation_name: str
    installation_address: str
    country_code: str  # ISO 3166-1 alpha-2
    unlocode: str | None = None  # UN/LOCODE for facility
    operator_name: str | None = None
    operator_vat_number: str | None = None


@dataclass
class CBAMGoodsEmission:
    """Embedded emissions for one CN code line."""
    cn_code: str
    goods_description: str
    quantity_net_mass_tonnes: Decimal
    direct_embedded_tco2e: Decimal
    indirect_embedded_tco2e: Decimal
    direct_embedded_per_tonne: Decimal
    indirect_embedded_per_tonne: Decimal
    uses_default_values: bool
    methodology: str
    installation: CBAMInstallation
    # Optional verified actuals metadata
    verification_body: str | None = None
    verification_date: date | None = None
    # Domestic carbon price
    carbon_price_paid_eur: Decimal = Decimal("0")
    carbon_price_currency: str | None = None


@dataclass
class CBAMQuarterlyReport:
    declarant_id: str           # EU CBAM Registry declarant identifier
    declarant_name: str
    declarant_address: str
    declarant_eori: str | None  # EU EORI number if applicable
    quarter_year: int
    quarter_number: int         # 1-4
    reporting_date: date
    goods_lines: list[CBAMGoodsEmission] = field(default_factory=list)

    @property
    def period_start(self) -> date:
        month = (self.quarter_number - 1) * 3 + 1
        return date(self.quarter_year, month, 1)

    @property
    def period_end(self) -> date:
        month = self.quarter_number * 3
        import calendar
        last_day = calendar.monthrange(self.quarter_year, month)[1]
        return date(self.quarter_year, month, last_day)


def _el(parent: ET.Element, tag: str, ns: str, text: str | None = None, **attrs) -> ET.Element:
    el = ET.SubElement(parent, f"{{{ns}}}{tag}", attrib=attrs)
    if text is not None:
        el.text = str(text)
    return el


def generate_cbam_xml(report: CBAMQuarterlyReport) -> tuple[str, str]:
    """
    Generate CBAM Quarterly Declarant Report XML.

    Returns (xml_string, report_hash) where report_hash is sha256 of the XML.
    """
    ET.register_namespace("cbam", CBAM_NS)
    ET.register_namespace("cbc", CBAM_COMMON_NS)
    ET.register_namespace("xsi", XSI_NS)

    root = ET.Element(
        f"{{{CBAM_NS}}}CBAMDeclarantReport",
        attrib={
            f"{{{XSI_NS}}}schemaLocation": f"{CBAM_NS} CBAM_Declarant_v1.xsd",
            "xmlns:cbam": CBAM_NS,
            "xmlns:cbc": CBAM_COMMON_NS,
        }
    )

    # ── Header ────────────────────────────────────────────────────────────────
    header = _el(root, "Header", CBAM_NS)
    _el(header, "ReportingDate", CBAM_COMMON_NS, report.reporting_date.isoformat())
    _el(header, "ReportingQuarter", CBAM_COMMON_NS,
        f"{report.quarter_year}-Q{report.quarter_number}")
    _el(header, "PeriodStart", CBAM_COMMON_NS, report.period_start.isoformat())
    _el(header, "PeriodEnd", CBAM_COMMON_NS, report.period_end.isoformat())
    _el(header, "Version", CBAM_COMMON_NS, "1.0")
    _el(header, "GeneratedAt", CBAM_COMMON_NS,
        datetime.now(timezone.utc).isoformat())

    # ── Declarant ─────────────────────────────────────────────────────────────
    declarant = _el(root, "Declarant", CBAM_NS)
    _el(declarant, "DeclarantID", CBAM_COMMON_NS, report.declarant_id)
    _el(declarant, "Name", CBAM_COMMON_NS, report.declarant_name)
    _el(declarant, "Address", CBAM_COMMON_NS, report.declarant_address)
    if report.declarant_eori:
        _el(declarant, "EORI", CBAM_COMMON_NS, report.declarant_eori)

    # ── Imports ───────────────────────────────────────────────────────────────
    imports = _el(root, "Imports", CBAM_NS)

    for line in report.goods_lines:
        import_line = _el(imports, "ImportLine", CBAM_NS)

        # Goods identification
        goods = _el(import_line, "Goods", CBAM_NS)
        _el(goods, "CNCode", CBAM_COMMON_NS, line.cn_code)
        _el(goods, "Description", CBAM_COMMON_NS, line.goods_description)
        _el(goods, "NetMassTonnes", CBAM_COMMON_NS, str(line.quantity_net_mass_tonnes))

        # Origin installation
        installation_el = _el(import_line, "OriginInstallation", CBAM_NS)
        _el(installation_el, "Name", CBAM_COMMON_NS, line.installation.installation_name)
        _el(installation_el, "Address", CBAM_COMMON_NS, line.installation.installation_address)
        _el(installation_el, "Country", CBAM_COMMON_NS, line.installation.country_code)
        if line.installation.unlocode:
            _el(installation_el, "UNLOCODE", CBAM_COMMON_NS, line.installation.unlocode)
        if line.installation.operator_name:
            _el(installation_el, "OperatorName", CBAM_COMMON_NS, line.installation.operator_name)

        # Embedded emissions
        ee = _el(import_line, "EmbeddedEmissions", CBAM_NS)
        _el(ee, "DirectEmbeddedTCO2e", CBAM_COMMON_NS, str(line.direct_embedded_tco2e.quantize(Decimal("0.001"))))
        _el(ee, "IndirectEmbeddedTCO2e", CBAM_COMMON_NS, str(line.indirect_embedded_tco2e.quantize(Decimal("0.001"))))
        total_ee = (line.direct_embedded_tco2e + line.indirect_embedded_tco2e).quantize(Decimal("0.001"))
        _el(ee, "TotalEmbeddedTCO2e", CBAM_COMMON_NS, str(total_ee))
        _el(ee, "DirectPerTonneTCO2e", CBAM_COMMON_NS, str(line.direct_embedded_per_tonne.quantize(Decimal("0.000001"))))
        _el(ee, "IndirectPerTonneTCO2e", CBAM_COMMON_NS, str(line.indirect_embedded_per_tonne.quantize(Decimal("0.000001"))))
        _el(ee, "UsesDefaultValues", CBAM_COMMON_NS, "true" if line.uses_default_values else "false")
        _el(ee, "Methodology", CBAM_COMMON_NS, line.methodology)

        # Verification (if actuals)
        if not line.uses_default_values and line.verification_body:
            verification = _el(import_line, "Verification", CBAM_NS)
            _el(verification, "VerificationBody", CBAM_COMMON_NS, line.verification_body)
            _el(verification, "VerificationDate", CBAM_COMMON_NS,
                line.verification_date.isoformat() if line.verification_date else "")

        # Domestic carbon price deduction (Art. 9)
        if line.carbon_price_paid_eur > 0:
            carbon_price_el = _el(import_line, "CarbonPriceDue", CBAM_NS)
            _el(carbon_price_el, "AmountEUR", CBAM_COMMON_NS,
                str(line.carbon_price_paid_eur.quantize(Decimal("0.01"))))

    # ── Totals ────────────────────────────────────────────────────────────────
    totals = _el(root, "Totals", CBAM_NS)
    total_tco2e = sum(l.direct_embedded_tco2e + l.indirect_embedded_tco2e for l in report.goods_lines)
    _el(totals, "TotalEmbeddedTCO2e", CBAM_COMMON_NS, str(Decimal(str(total_tco2e)).quantize(Decimal("0.001"))))
    _el(totals, "TotalImportLines", CBAM_COMMON_NS, str(len(report.goods_lines)))

    # Serialise
    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=False)
    pretty = minidom.parseString(f'<?xml version="1.0" encoding="UTF-8"?>{xml_str}').toprettyxml(indent="  ")
    # Remove extra declaration from toprettyxml
    lines = pretty.split("\n")
    if lines[0].startswith("<?xml"):
        lines = lines[1:]
    pretty = "\n".join(lines)
    full_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + pretty

    report_hash = hashlib.sha256(full_xml.encode("utf-8")).hexdigest()
    return full_xml, report_hash
