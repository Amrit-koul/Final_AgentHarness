"""Bank-owned versioned prompt loading with optional LangSmith Hub override."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from threading import RLock
from typing import Any

import yaml

from agent_harness.tracing import get_tracer


PROMPT_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class PromptDefinition:
    prompt_id: str
    version: str
    owner: str
    business_function: str
    description: str
    input_variables: list[str]
    template: str
    expected_output: str
    safety_notes: str
    source: str = "local"
    environment: str = "local"
    name: str = ""

    def render(self, **variables: Any) -> str:
        missing = [key for key in self.input_variables if key not in variables]
        if missing:
            raise ValueError(f"Missing prompt variables for {self.prompt_id}: {', '.join(missing)}")
        return self.template.format(**{key: variables[key] for key in self.input_variables})


class PromptManager:
    def __init__(self, root: Path = PROMPT_ROOT, environment: str | None = None):
        self.root = Path(root)
        self.environment = environment or os.getenv("PROMPT_ENV", os.getenv("APP_ENV", "local"))
        self._cache: dict[tuple[str, str, str], PromptDefinition] = {}
        self._lock = RLock()

    def get_prompt(self, prompt_id: str, version: str = "v1") -> PromptDefinition:
        key = (prompt_id, version, self.environment)
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        local = self._load_local(prompt_id, version)
        prompt = self._pull_langsmith(local) if self._hub_enabled else local
        with self._lock:
            self._cache[key] = prompt
        with get_tracer().span("prompt_template_load", inputs={"prompt_id": prompt_id, "version": version}, metadata=self.trace_metadata(prompt)) as span:
            span.set_output({"loaded": True, "source": prompt.source})
        return prompt

    def render(self, prompt_id: str, version: str = "v1", **variables: Any) -> tuple[str, PromptDefinition]:
        prompt = self.get_prompt(prompt_id, version)
        with get_tracer().span("prompt_render", inputs={"input_variable_keys": sorted(variables)}, metadata=self.trace_metadata(prompt)) as span:
            rendered = prompt.render(**variables)
            span.set_output({"rendered": True, "character_count": len(rendered)})
        return rendered, prompt

    @staticmethod
    def trace_metadata(prompt: PromptDefinition) -> dict:
        return {
            "prompt_id": prompt.prompt_id, "prompt_name": prompt.name or prompt.prompt_id,
            "prompt_version": prompt.version, "prompt_source": prompt.source,
            "prompt_environment": prompt.environment, "input_variable_keys": prompt.input_variables,
        }

    @property
    def _hub_enabled(self) -> bool:
        enabled = os.getenv("LANGSMITH_PROMPTS_ENABLED", "").lower() in {"1", "true", "yes", "on"}
        return enabled and bool(os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY"))

    def _load_local(self, prompt_id: str, version: str) -> PromptDefinition:
        matches = list(self.root.glob(f"**/{prompt_id}.{version}.yaml"))
        if not matches:
            raise KeyError(f"Prompt '{prompt_id}' version '{version}' was not found under {self.root}")
        raw = yaml.safe_load(matches[0].read_text(encoding="utf-8")) or {}
        return PromptDefinition(**{key: raw.get(key, "") for key in PromptDefinition.__dataclass_fields__ if key not in {"source", "environment", "name"}}, source="local", environment=self.environment, name=matches[0].stem)

    def _pull_langsmith(self, local: PromptDefinition) -> PromptDefinition:
        identifier = os.getenv(f"LANGSMITH_PROMPT_{local.prompt_id.upper()}", f"{local.prompt_id}:{self.environment}")
        try:
            from langsmith import Client
            pulled = Client().pull_prompt(identifier)
            template = self._template_from_hub(pulled)
            if not template:
                return local
            return PromptDefinition(**{**local.__dict__, "template": template, "source": "langsmith", "name": identifier})
        except Exception:
            return local

    @staticmethod
    def _template_from_hub(prompt: Any) -> str | None:
        if isinstance(getattr(prompt, "template", None), str):
            return prompt.template
        messages = getattr(prompt, "messages", None)
        if messages:
            parts = []
            for message in messages:
                nested = getattr(message, "prompt", message)
                template = getattr(nested, "template", None)
                if isinstance(template, str): parts.append(template)
            return "\n\n".join(parts) or None
        return None


prompt_manager = PromptManager()
