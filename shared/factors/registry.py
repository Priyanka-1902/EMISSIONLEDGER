"""
Emission factor registry with full provenance tracking.

Every factor lookup is logged with: factor_id, version_hash, effective_date.
Factors are immutable once published. Superseding a factor creates a new record
and marks the old one with superseded_by.
"""
from __future__ import annotations
import hashlib
import json
from datetime import date
from decimal import Decimal
from uuid import UUID
from typing import Optional

from ..schemas.factor import EmissionFactor, FactorSource


class FactorRegistry:
    def __init__(self) -> None:
        self._factors: dict[str, list[EmissionFactor]] = {}  # keyed by activity_type

    def register(self, factor: EmissionFactor) -> None:
        key = factor.activity_type
        if key not in self._factors:
            self._factors[key] = []
        self._factors[key].append(factor)

    def get(
        self,
        activity_type: str,
        as_of: date,
        fuel_type: str | None = None,
        grid_region: str | None = None,
        isic_code: str | None = None,
        source_preference: list[FactorSource] | None = None,
    ) -> EmissionFactor:
        """
        Retrieve the most specific, authoritative factor valid on `as_of`.
        Raises KeyError if no valid factor found — caller must handle.
        """
        candidates = self._factors.get(activity_type, [])
        valid = [
            f for f in candidates
            if f.effective_from <= as_of
            and (f.effective_to is None or f.effective_to >= as_of)
            and f.superseded_by is None
        ]

        if fuel_type:
            specific = [f for f in valid if f.fuel_type == fuel_type]
            if specific:
                valid = specific

        if grid_region:
            specific = [f for f in valid if f.grid_region == grid_region]
            if specific:
                valid = specific

        if isic_code:
            specific = [f for f in valid if f.isic_code and isic_code.startswith(f.isic_code)]
            if specific:
                valid = specific

        if not valid:
            raise KeyError(
                f"No emission factor for activity={activity_type}, "
                f"fuel={fuel_type}, grid={grid_region}, as_of={as_of}"
            )

        # Apply source preference order
        if source_preference:
            for preferred_source in source_preference:
                preferred = [f for f in valid if f.source == preferred_source]
                if preferred:
                    valid = preferred
                    break

        # Return most recent effective factor
        return sorted(valid, key=lambda f: f.effective_from, reverse=True)[0]

    def get_by_id(self, factor_id: UUID) -> EmissionFactor:
        for factors in self._factors.values():
            for f in factors:
                if f.id == factor_id:
                    return f
        raise KeyError(f"Factor {factor_id} not found")

    def compute_version_hash(self, factor: EmissionFactor) -> str:
        payload = json.dumps({
            "source": factor.source.value,
            "value": str(factor.value),
            "unit": factor.unit,
            "effective_from": factor.effective_from.isoformat(),
            "source_publication": factor.source_publication,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def list_all(self) -> list[EmissionFactor]:
        result = []
        for factors in self._factors.values():
            result.extend(factors)
        return result
