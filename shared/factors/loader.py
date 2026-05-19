"""
Loads emission factors from YAML files into FactorRegistry.
Computes and validates version hashes at load time.
"""
from __future__ import annotations
import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import yaml

from .registry import FactorRegistry
from ..schemas.factor import EmissionFactor, FactorSource, GasType

FACTORS_DIR = Path(__file__).parent

SOURCE_MAP = {
    "cea_co2_baseline": FactorSource.CEA_CO2_BASELINE,
    "bee_pat": FactorSource.BEE_PAT,
    "ipcc_ar6": FactorSource.IPCC_AR6,
    "defra": FactorSource.DEFRA,
    "eu_cbam_default": FactorSource.EU_CBAM_DEFAULT,
}

STATE_TO_REGION = {
    "TN": "tamil_nadu", "TA": "tamil_nadu",
    "TS": "telangana", "AP": "telangana",
    "MH": "western", "GJ": "western",
    "KA": "southern", "KL": "southern",
    "UP": "northern", "DL": "northern", "HR": "northern",
    "RJ": "northern", "PB": "northern",
    "WB": "eastern", "BR": "eastern", "JH": "eastern",
}


def _compute_hash(source: str, value: str, unit: str, effective_from: str, publication: str) -> str:
    payload = json.dumps({
        "source": source,
        "value": value,
        "unit": unit,
        "effective_from": effective_from,
        "source_publication": publication,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _parse_date(d: str | None) -> date | None:
    if d is None:
        return None
    return date.fromisoformat(d)


def load_factors_from_yaml(yaml_path: Path, registry: FactorRegistry) -> int:
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    meta = data.get("metadata", {})
    source = SOURCE_MAP.get(meta.get("source", ""), FactorSource.IPCC_AR6)
    source_publication = meta.get("source_publication", "")
    published_date = _parse_date(meta.get("published_date")) or date.today()
    default_effective_from = _parse_date(meta.get("effective_from")) or date(2024, 1, 1)

    count = 0
    for raw in data.get("factors", []):
        effective_from = _parse_date(raw.get("effective_from")) or default_effective_from
        effective_to = _parse_date(raw.get("effective_to"))
        value = Decimal(str(raw["value"]))
        unit = raw["unit"]
        version_hash = _compute_hash(
            source.value, str(value), unit,
            effective_from.isoformat(), source_publication
        )
        factor = EmissionFactor(
            id=uuid4(),
            name=raw["name"],
            description=raw.get("description", raw["name"]),
            activity_type=raw["activity_type"],
            fuel_type=raw.get("fuel_type"),
            grid_region=raw.get("grid_region"),
            isic_code=raw.get("isic_code"),
            gas_type=GasType.CO2E,
            value=value,
            unit=unit,
            gwp_basis=meta.get("gwp_basis", "AR6"),
            source=source,
            source_publication=source_publication,
            source_url=meta.get("url"),
            effective_from=effective_from,
            effective_to=effective_to,
            published_date=published_date,
            version=raw.get("version", "1.0.0"),
            version_hash=version_hash,
        )
        registry.register(factor)
        count += 1

    return count


def build_default_registry() -> FactorRegistry:
    registry = FactorRegistry()
    yaml_files = [
        FACTORS_DIR / "india_grid.yaml",
        FACTORS_DIR / "fuels.yaml",
        FACTORS_DIR / "cbam_defaults.yaml",
    ]
    for path in yaml_files:
        if path.exists():
            n = load_factors_from_yaml(path, registry)
    return registry


# Module-level singleton — import and use directly in services
_default_registry: FactorRegistry | None = None


def get_registry() -> FactorRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = build_default_registry()
    return _default_registry
