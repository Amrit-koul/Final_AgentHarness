"""Generic governance view over injected rules or an explicit YAML path."""
from pathlib import Path
import logging
import yaml


class GovernanceReader:
    def __init__(self, config_path=None, rules=None, event_source=None):
        self.event_source = event_source
        self._config = dict(rules or {})
        if config_path:
            try:
                with Path(config_path).open("r", encoding="utf-8") as handle: self._config = yaml.safe_load(handle) or {}
            except Exception: logging.exception("Failed to load governance configuration")

    def get_rules(self):
        result = []
        for category, values in self._config.items():
            if not isinstance(values, dict): continue
            for key, value in values.items():
                result.append({"id": f"{category}.{key}", "category": category, "description": key.replace("_", " ").title(), "value": value, "status": "active"})
        return result

    def get_governance_summary(self):
        rules = self.get_rules(); events = self.event_source() if self.event_source else []
        return {"rules": rules, "rule_count": len(rules), "trigger_log": events, "trigger_count_recent": len(events)}


# Empty generic default retained for import compatibility; applications inject configuration.
governance_reader = GovernanceReader()
