"""Bank-specific governance projection for the existing harness dashboard API."""
from pathlib import Path

from agent_harness.audit import audit_store
from agent_harness.config_loader import load_yaml


class BankingGovernanceReader:
    def __init__(self, config_path=None):
        self.config_path = config_path or Path(__file__).parent / "config" / "guardrails.yaml"
        self._config = load_yaml(self.config_path)

    def get_rules(self):
        rules, config = [], self._config
        mappings = {
            "input": (("min_length", "Minimum query length (characters)"), ("max_length", "Maximum query length (characters)"), ("injection_patterns", "Prompt injection patterns")),
            "orchestrator": (("max_iterations", "Maximum reasoning iterations"), ("max_subtasks", "Maximum decomposed tasks"), ("per_hop_timeout_seconds", "Per-hop timeout (seconds)")),
            "rag": (("hard_distance_threshold", "RAG hard-block threshold"), ("soft_distance_threshold", "RAG low-confidence threshold")),
        }
        for category, fields in mappings.items():
            for key, description in fields:
                if key in config.get(category, {}):
                    value = config[category][key]
                    rules.append({"id": f"{category}.{key}", "category": category, "description": description, "value": len(value) if isinstance(value, list) else value, "status": "active"})
        for intent, text in config.get("output", {}).get("intent_disclaimers", {}).items():
            rules.append({"id": f"output.disclaimer.{intent}", "category": "output", "description": f"Mandatory disclaimer for {intent}", "value": text, "status": "active"})
        return rules

    def get_governance_summary(self):
        rules = self.get_rules(); events = audit_store.get_guardrail_events(limit=50)
        return {"rules": rules, "rule_count": len(rules), "trigger_log": events, "trigger_count_recent": len(events)}


governance_reader = BankingGovernanceReader()
