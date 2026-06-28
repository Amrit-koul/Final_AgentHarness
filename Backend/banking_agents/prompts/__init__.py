from pathlib import Path

from agent_harness.prompt_registry import PromptRegistry

from .manager import PromptDefinition, PromptManager, prompt_manager


PROMPT_ROOT = Path(__file__).resolve().parent
prompt_registry = PromptRegistry(PROMPT_ROOT)

__all__ = ["PromptDefinition", "PromptManager", "PromptRegistry", "prompt_manager", "prompt_registry"]
