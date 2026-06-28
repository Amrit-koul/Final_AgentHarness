"""Read-only, application-configured catalogues for visible agent primitives."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml


def _yaml(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or (default if default is not None else {})


class PrimitiveCatalog:
    """Generic registry facade. Domain applications supply YAML and agent manifests."""

    def __init__(self, config_dir: str | Path, prompt_root: str | Path, registry):
        self.config_dir = Path(config_dir)
        self.prompt_root = Path(prompt_root)
        self.registry = registry
        self.skills = self._load("skills.yaml", "skills")
        self.tools = self._load("tools.yaml", "tools")
        self.memory_contracts = self._load("memory_contracts.yaml", "memory_contracts")
        self.hooks = self._load("hooks.yaml", "hooks")
        self.evaluators = self._load("evaluators.yaml", "evaluators")

    def _load(self, filename: str, key: str) -> dict[str, dict]:
        raw = _yaml(self.config_dir / filename, {})
        items = raw.get(key, raw) if isinstance(raw, dict) else {}
        return {item_id: {"%s_id" % key[:-1] if key.endswith("s") else "id": item_id, **(value or {})}
                for item_id, value in items.items()}

    def _agents(self):
        return [contract.to_dict() for contract in self.registry._contracts.values()]

    @staticmethod
    def _id(item: dict, collection: str) -> str:
        return item.get(f"{collection[:-1]}_id") or item.get("hook_id") or item.get("evaluator_id") or item.get("memory_contract_id")

    def list_skills(self):
        return [self.skill(skill_id) for skill_id in sorted(self.skills)]

    def skill(self, skill_id: str):
        if skill_id not in self.skills:
            raise KeyError(skill_id)
        item = dict(self.skills[skill_id])
        agents = [a["agent_id"] for a in self._agents() if skill_id in a.get("skills", [])]
        item.update({"skill_id": skill_id, "agents": agents,
                     "related_tools": sorted({tool for a in self._agents() if a["agent_id"] in agents for tool in a.get("tools", [])})})
        return item

    def list_tools(self):
        return [self.tool(tool_id) for tool_id in sorted(self.tools)]

    def tool(self, tool_id: str):
        if tool_id not in self.tools:
            raise KeyError(tool_id)
        item = dict(self.tools[tool_id])
        item["tool_id"] = tool_id
        item["agents"] = [a["agent_id"] for a in self._agents() if tool_id in a.get("tools", [])]
        return item

    def list_memory_contracts(self):
        return [self.memory_contract(scope) for scope in sorted(self.memory_contracts)]

    def memory_contract(self, scope: str):
        if scope not in self.memory_contracts:
            raise KeyError(scope)
        return {"memory_scope": scope, **self.memory_contracts[scope]}

    def list_hooks(self):
        return [self.hook(hook_id) for hook_id in sorted(self.hooks)]

    def hook(self, hook_id: str):
        if hook_id not in self.hooks:
            raise KeyError(hook_id)
        return {"hook_id": hook_id, **self.hooks[hook_id]}

    def list_evaluators(self):
        return [self.evaluator(evaluator_id) for evaluator_id in sorted(self.evaluators)]

    def evaluator(self, evaluator_id: str):
        if evaluator_id not in self.evaluators:
            raise KeyError(evaluator_id)
        return {"evaluator_id": evaluator_id, **self.evaluators[evaluator_id]}

    def prompts(self):
        """Unifies Markdown prompt packages and versioned YAML prompt definitions."""
        entries: dict[str, dict] = {}
        for folder in self.prompt_root.iterdir() if self.prompt_root.exists() else []:
            if folder.is_dir() and (folder / "metadata.yaml").exists():
                meta = _yaml(folder / "metadata.yaml", {})
                prompt_id = meta.get("prompt_id", folder.name)
                digest = sha256(b"".join(p.read_bytes() for p in sorted(folder.iterdir()) if p.is_file())).hexdigest()
                entries[prompt_id] = {"prompt_id": prompt_id, "version": str(meta.get("version", "v1")), "source": "local_markdown", "file_path": str(folder), "owner": meta.get("owner", "Banking Agents"), "business_function": meta.get("business_function", "generic"), "status": meta.get("status", "active"), "hash": digest}
        for path in self.prompt_root.glob("**/*.yaml"):
            if path.name == "metadata.yaml":
                continue
            raw = _yaml(path, {})
            if not isinstance(raw, dict) or not raw.get("prompt_id"):
                continue
            prompt_id = raw["prompt_id"]
            entries[prompt_id] = {"prompt_id": prompt_id, "version": str(raw.get("version", "v1")), "source": "local_yaml", "file_path": str(path), "owner": raw.get("owner", "Banking Agents"), "business_function": raw.get("business_function", "generic"), "status": raw.get("status", "active"), "hash": sha256(path.read_bytes()).hexdigest()}
        for item in entries.values():
            item["agents_using_it"] = [a["agent_id"] for a in self._agents() if any(ref.split(":")[0] == item["prompt_id"] for ref in a.get("prompts", []))]
        return sorted(entries.values(), key=lambda item: item["prompt_id"])

    def prompt(self, prompt_id: str):
        return next((item for item in self.prompts() if item["prompt_id"] == prompt_id), None)

    def validation(self):
        warnings, errors, missing_skills, missing_tools, risky = [], [], [], [], []
        skill_map, tool_map = {}, {}
        for agent in self._agents():
            agent_id = agent["agent_id"]
            skill_map[agent_id], tool_map[agent_id] = agent.get("skills", []), agent.get("tools", [])
            for skill in agent.get("skills", []):
                if skill not in self.skills:
                    missing_skills.append({"agent_id": agent_id, "skill_id": skill})
                    warnings.append({"code": "unknown_skill_reference", "agent_id": agent_id, "reference": skill})
            for tool in agent.get("tools", []):
                definition = self.tools.get(tool)
                if not definition:
                    missing_tools.append({"agent_id": agent_id, "tool_id": tool})
                    warnings.append({"code": "unknown_tool_reference", "agent_id": agent_id, "reference": tool})
                    continue
                allowed = definition.get("allowed_agent_ids", ["*"])
                if "*" not in allowed and agent_id not in allowed:
                    warnings.append({"code": "unauthorized_tool_reference", "agent_id": agent_id, "reference": tool})
                if definition.get("risk_tier", definition.get("risk")) in {"high", "critical"} and not definition.get("guardrails"):
                    risky.append({"agent_id": agent_id, "tool_id": tool})
                    warnings.append({"code": "high_risk_tool_without_guardrail", "agent_id": agent_id, "reference": tool})
        return {"valid": not errors, "warnings": warnings, "errors": errors, "agent_skill_map": skill_map, "agent_tool_map": tool_map, "missing_skill_refs": missing_skills, "missing_tool_refs": missing_tools, "high_risk_without_guardrail": risky}

    def agent_primitives(self, agent_id: str):
        agent = next(a for a in self._agents() if a["agent_id"] == agent_id)
        validation = self.validation()
        hook_points = set()
        if agent.get("observability_hooks", {}).get("execution_trace"): hook_points.add("on_trace_emit")
        if agent.get("observability_hooks", {}).get("agent_run"): hook_points.update({"pre_invoke", "post_invoke"})
        if agent.get("observability_hooks", {}).get("step_trace"): hook_points.update({"pre_tool", "post_tool"})
        if agent.get("observability_hooks", {}).get("policy_decision"): hook_points.update({"post_guardrail", "on_policy_block"})
        return {"skills": [self.skill(x) if x in self.skills else {"skill_id": x, "status": "unregistered"} for x in agent.get("skills", [])],
                "tools": [self.tool(x) if x in self.tools else {"tool_id": x, "status": "unregistered"} for x in agent.get("tools", [])],
                "memory_contracts": [item for item in self.list_memory_contracts() if "*" in item.get("allowed_agent_ids", []) or agent_id in item.get("allowed_agent_ids", [])],
                "hooks": [item for item in self.list_hooks() if item.get("trigger_point") in hook_points],
                "prompts": [item for item in self.prompts() if agent_id in item["agents_using_it"]],
                "evaluators": [item for item in self.list_evaluators() if item.get("applies_to", "generic").lower() in {"generic", agent.get("business_function", "").lower().split()[0]}],
                "validation_warnings": [w for w in validation["warnings"] if w["agent_id"] == agent_id]}


class HookDispatcher:
    """Safe hook event recorder; it deliberately does not execute third-party code."""
    def __init__(self, store, catalog: PrimitiveCatalog):
        self.store, self.catalog = store, catalog

    def emit(self, hook_name: str, payload: dict):
        hook = next((item for item in self.catalog.list_hooks() if item.get("trigger_point") == hook_name or item["hook_id"] == hook_name), None)
        if not hook or not hook.get("enabled", True):
            return {"emitted": False, "reason": "not_configured"}
        self.store.add_event("HOOK_" + hook_name.upper(), payload.get("trace_id", ""), payload.get("agent_id", ""), {"hook_id": hook["hook_id"], "payload": payload})
        return {"emitted": True, "hook_id": hook["hook_id"]}
