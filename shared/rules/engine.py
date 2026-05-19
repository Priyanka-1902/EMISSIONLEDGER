"""
Version-controlled compliance rules engine.

Rules are stored as JSON Schema documents with effective_from / effective_to dates.
Every rule change is logged with author, approval chain, and diff.
The engine evaluates rules against emission records and report data.
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class RuleSeverity(str, Enum):
    ERROR = "error"      # Blocks report generation
    WARNING = "warning"  # Shows in UI, doesn't block
    INFO = "info"        # Informational annotation


class RuleCategory(str, Enum):
    CBAM = "cbam"
    GHG_PROTOCOL = "ghg_protocol"
    BEE_PAT = "bee_pat"
    BRSR = "brsr"
    DATA_QUALITY = "data_quality"
    TENANT_CONFIG = "tenant_config"


@dataclass
class ComplianceRule:
    id: str
    name: str
    description: str
    category: RuleCategory
    severity: RuleSeverity
    effective_from: date
    effective_to: date | None
    version: str
    version_hash: str
    regulation_reference: str
    condition: dict  # JSON Schema-style condition
    message_template: str  # e.g. "Scope 1 data missing for {facility}"
    remediation_url: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None


@dataclass
class RuleResult:
    rule_id: str
    rule_name: str
    severity: RuleSeverity
    passed: bool
    message: str
    affected_record_ids: list[str] = field(default_factory=list)
    remediation_url: str | None = None


class RulesEngine:
    def __init__(self) -> None:
        self._rules: list[ComplianceRule] = []

    def register(self, rule: ComplianceRule) -> None:
        self._rules.append(rule)

    def evaluate(
        self,
        context: dict[str, Any],
        as_of: date,
        categories: list[RuleCategory] | None = None,
    ) -> list[RuleResult]:
        results = []
        active_rules = [
            r for r in self._rules
            if r.effective_from <= as_of
            and (r.effective_to is None or r.effective_to >= as_of)
            and (categories is None or r.category in categories)
        ]
        for rule in active_rules:
            result = self._evaluate_rule(rule, context)
            results.append(result)
        return results

    def get_blocking_errors(self, results: list[RuleResult]) -> list[RuleResult]:
        return [r for r in results if not r.passed and r.severity == RuleSeverity.ERROR]

    def compute_rule_hash(self, rule: ComplianceRule) -> str:
        payload = json.dumps({
            "id": rule.id,
            "condition": rule.condition,
            "effective_from": rule.effective_from.isoformat(),
            "version": rule.version,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _evaluate_rule(self, rule: ComplianceRule, context: dict) -> RuleResult:
        try:
            passed = self._check_condition(rule.condition, context)
        except Exception as e:
            passed = False
            return RuleResult(
                rule_id=rule.id,
                rule_name=rule.name,
                severity=RuleSeverity.ERROR,
                passed=False,
                message=f"Rule evaluation error: {e}",
            )
        message = rule.message_template if not passed else f"{rule.name}: OK"
        # Simple template substitution
        for key, val in context.items():
            message = message.replace(f"{{{key}}}", str(val))
        return RuleResult(
            rule_id=rule.id,
            rule_name=rule.name,
            severity=rule.severity,
            passed=passed,
            message=message,
            remediation_url=rule.remediation_url,
        )

    def _check_condition(self, condition: dict, context: dict) -> bool:
        """
        Evaluate a JSON Schema-style condition against context.
        Supports: required, minimum, maximum, enum, allOf, anyOf, not.
        """
        ctype = condition.get("type")

        if "allOf" in condition:
            return all(self._check_condition(c, context) for c in condition["allOf"])
        if "anyOf" in condition:
            return any(self._check_condition(c, context) for c in condition["anyOf"])
        if "not" in condition:
            return not self._check_condition(condition["not"], context)

        if "required" in condition:
            for field_path in condition["required"]:
                if not self._get_nested(context, field_path.split(".")):
                    return False

        if "properties" in condition:
            for field_path, constraints in condition["properties"].items():
                value = self._get_nested(context, field_path.split("."))
                if not self._check_constraints(value, constraints, context):
                    return False

        return True

    def _check_constraints(self, value: Any, constraints: dict, context: dict) -> bool:
        if "minimum" in constraints and (value is None or float(value) < constraints["minimum"]):
            return False
        if "maximum" in constraints and (value is None or float(value) > constraints["maximum"]):
            return False
        if "enum" in constraints and value not in constraints["enum"]:
            return False
        if "minLength" in constraints and (not value or len(str(value)) < constraints["minLength"]):
            return False
        if "pattern" in constraints:
            import re
            if not re.match(constraints["pattern"], str(value or "")):
                return False
        return True

    def _get_nested(self, obj: dict, keys: list[str]) -> Any:
        for key in keys:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
        return obj
