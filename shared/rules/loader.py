from __future__ import annotations
import hashlib
import json
from datetime import date, datetime
from pathlib import Path

from .engine import ComplianceRule, RulesEngine, RuleCategory, RuleSeverity

RULES_DIR = Path(__file__).parent


def load_rules_from_json(json_path: Path, engine: RulesEngine) -> int:
    with open(json_path) as f:
        data = json.load(f)
    effective_from = date.fromisoformat(data.get("effective_from", "2024-01-01"))
    count = 0
    for raw in data.get("rules", []):
        condition = raw.get("condition", {})
        version_hash = hashlib.sha256(
            json.dumps({"id": raw["id"], "condition": condition}, sort_keys=True).encode()
        ).hexdigest()
        rule = ComplianceRule(
            id=raw["id"],
            name=raw["name"],
            description=raw["description"],
            category=RuleCategory(raw["category"]),
            severity=RuleSeverity(raw["severity"]),
            effective_from=effective_from,
            effective_to=None,
            version=data.get("version", "1.0.0"),
            version_hash=version_hash,
            regulation_reference=raw.get("regulation_reference", ""),
            condition=condition,
            message_template=raw.get("message_template", ""),
            remediation_url=raw.get("remediation_url"),
        )
        engine.register(rule)
        count += 1
    return count


def build_default_engine() -> RulesEngine:
    engine = RulesEngine()
    json_files = [
        RULES_DIR / "cbam_rules.json",
    ]
    for path in json_files:
        if path.exists():
            load_rules_from_json(path, engine)
    return engine
