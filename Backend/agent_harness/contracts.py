"""Portable agent contracts for the reusable control-plane framework."""
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class AgentStatus(str, Enum):
    ACTIVE = "active"
    REVIEW = "review"
    DISABLED = "disabled"
    QUARANTINED = "quarantined"


@dataclass
class AgentContract:
    agent_id: str
    name: str
    owner: str
    business_function: str
    agent_type: str
    execution_mode: str
    adapter_type: str
    entrypoint: str = ""
    endpoint: str = ""
    version: str = "1.0.0"
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    state_schema: dict[str, Any] = field(default_factory=dict)
    memory_schema: dict[str, Any] = field(default_factory=dict)
    skills: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)
    model_preferences: dict[str, Any] = field(default_factory=dict)
    policy_permissions: dict[str, Any] = field(default_factory=dict)
    guardrails: list[str] = field(default_factory=list)
    observability_hooks: dict[str, Any] = field(default_factory=dict)
    status: AgentStatus = AgentStatus.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw):
        known = set(cls.__dataclass_fields__)
        values = {key: value for key, value in raw.items() if key in known}
        values["status"] = AgentStatus(values.get("status", "active"))
        values["metadata"] = {**raw.get("metadata", {}), **{key: value for key, value in raw.items() if key not in known}}
        return cls(**values)

    def to_dict(self):
        result = asdict(self)
        result["status"] = self.status.value
        return result


AgentManifest = AgentContract
AgentPluginContract = AgentContract
