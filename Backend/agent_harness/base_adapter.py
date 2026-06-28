"""Generic adapter lifecycle with injected services."""
import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone


class BaseAgentAdapter(ABC):
    def __init__(self, manifest, services=None):
        self.manifest, self.services = manifest, services
        self._states, self._memory = {}, {}

    def validate_input(self, payload):
        if not isinstance(payload, dict): raise ValueError("Agent input must be a JSON object")
        missing = [key for key in self.manifest.input_schema.get("required", []) if key not in payload]
        if missing: raise ValueError(f"Missing required input fields: {', '.join(missing)}")
        return payload

    @abstractmethod
    def invoke(self, payload, trace_id): ...

    async def invoke_async(self, payload, trace_id): return await asyncio.to_thread(self.invoke, payload, trace_id)
    def get_state(self, trace_id): return self._states.get(trace_id, {})
    def save_state(self, trace_id, state): self._states[trace_id] = state

    def load_memory(self, entity_id):
        if self.services and getattr(self.services, "store", None):
            rows = self.services.store.query("SELECT memory_json FROM agent_memory WHERE agent_id=? AND entity_id=?", (self.manifest.agent_id, entity_id))
            if rows: return json.loads(rows[0]["memory_json"])
        return self._memory.get(entity_id, {})

    def save_memory(self, entity_id, memory):
        self._memory[entity_id] = memory
        if self.services and getattr(self.services, "store", None):
            self.services.store.execute("INSERT OR REPLACE INTO agent_memory(agent_id,entity_id,memory_json,updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP)", (self.manifest.agent_id, entity_id, json.dumps(memory, default=str)))

    def emit_event(self, event_type, payload):
        if self.services and getattr(self.services, "trace_provider", None):
            self.services.trace_provider.emit(event_type, payload.get("trace_id", ""), self.manifest.agent_id, payload)

    def check_policy(self, action, context): return self.services.policy.check(self.manifest.agent_id, action, context).to_dict() if self.services else {"decision": "ALLOW"}
    def handle_policy_decision(self, decision, context):
        if decision.get("decision") == "BLOCK": raise PermissionError(decision.get("reason", "Policy blocked"))
    def get_health(self):
        return {
            "status": "n/a",
            "agent_id": self.manifest.agent_id,
            "last_checked": datetime.now(timezone.utc).isoformat(),
            "details": {"adapter_type": self.manifest.adapter_type},
        }
