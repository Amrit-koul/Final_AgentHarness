"""Markdown-backed prompt registry for agent harness prompts.

Long prompt bodies live in Markdown files. YAML is intentionally limited to
metadata so prompts can be reviewed, versioned, and hashed cleanly.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import yaml


REQUIRED_PROMPT_FILES = ("system.md", "developer.md", "few_shots.md", "metadata.yaml")
OPTIONAL_SCHEMA_FILE = "output_schema.json"


class PromptRegistryError(RuntimeError):
    """Raised when a prompt folder is malformed or cannot be loaded."""


@dataclass(frozen=True)
class LoadedPrompt:
    prompt_id: str
    version: str
    metadata: dict[str, Any]
    files_loaded: list[str]
    prompt_hash: str
    system: str
    developer: str
    few_shots: str
    output_schema: dict[str, Any] | None = None

    @property
    def text(self) -> str:
        return "\n\n".join(
            [
                "# System\n" + self.system.strip(),
                "# Developer\n" + self.developer.strip(),
                "# Few-shot Examples\n" + self.few_shots.strip(),
            ]
        )

    def public_dict(self, *, include_text: bool = False) -> dict[str, Any]:
        payload = {
            "prompt_id": self.prompt_id,
            "version": self.version,
            "metadata": self.metadata,
            "files_loaded": self.files_loaded,
            "prompt_hash": self.prompt_hash,
            "has_output_schema": self.output_schema is not None,
        }
        if self.output_schema is not None:
            payload["output_schema"] = self.output_schema
        if include_text:
            payload["text"] = self.text
            payload["sections"] = {
                "system": self.system,
                "developer": self.developer,
                "few_shots": self.few_shots,
            }
        return payload


class PromptRegistry:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def list_prompt_ids(self) -> list[str]:
        if not self.root.exists():
            raise PromptRegistryError(f"Prompt root does not exist: {self.root}")
        return sorted(
            path.name
            for path in self.root.iterdir()
            if path.is_dir() and (path / "metadata.yaml").exists()
        )

    def list_prompts(self) -> list[dict[str, Any]]:
        return [
            self.load(prompt_id).public_dict(include_text=False)
            for prompt_id in self.list_prompt_ids()
        ]

    def load(self, prompt_id: str) -> LoadedPrompt:
        if not prompt_id or any(part in prompt_id for part in ("..", "/", "\\")):
            raise PromptRegistryError(f"Invalid prompt_id: {prompt_id!r}")

        folder = (self.root / prompt_id).resolve()
        try:
            folder.relative_to(self.root)
        except ValueError as exc:
            raise PromptRegistryError(f"Prompt path escapes registry root: {prompt_id}") from exc

        if not folder.exists() or not folder.is_dir():
            raise PromptRegistryError(f"Prompt '{prompt_id}' was not found under {self.root}")

        missing = [name for name in REQUIRED_PROMPT_FILES if not (folder / name).is_file()]
        if missing:
            raise PromptRegistryError(
                f"Prompt '{prompt_id}' is missing required file(s): {', '.join(missing)}"
            )

        metadata = self._read_yaml(folder / "metadata.yaml", prompt_id)
        declared_id = metadata.get("prompt_id")
        if declared_id != prompt_id:
            raise PromptRegistryError(
                f"Prompt '{prompt_id}' metadata prompt_id mismatch: {declared_id!r}"
            )
        version = str(metadata.get("version") or "").strip()
        if not version:
            raise PromptRegistryError(f"Prompt '{prompt_id}' metadata.yaml must define version")

        system = self._read_text(folder / "system.md", prompt_id)
        developer = self._read_text(folder / "developer.md", prompt_id)
        few_shots = self._read_text(folder / "few_shots.md", prompt_id)
        files_loaded = ["system.md", "developer.md", "few_shots.md", "metadata.yaml"]

        output_schema = None
        schema_path = folder / OPTIONAL_SCHEMA_FILE
        if schema_path.exists():
            output_schema = self._read_json(schema_path, prompt_id)
            files_loaded.append(OPTIONAL_SCHEMA_FILE)

        digest = sha256()
        for filename in files_loaded:
            digest.update(filename.encode("utf-8"))
            digest.update(b"\0")
            digest.update((folder / filename).read_bytes())
            digest.update(b"\0")

        return LoadedPrompt(
            prompt_id=prompt_id,
            version=version,
            metadata=metadata,
            files_loaded=files_loaded,
            prompt_hash=digest.hexdigest(),
            system=system,
            developer=developer,
            few_shots=few_shots,
            output_schema=output_schema,
        )

    @staticmethod
    def _read_text(path: Path, prompt_id: str) -> str:
        try:
            value = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise PromptRegistryError(f"Unable to read {path.name} for prompt '{prompt_id}': {exc}") from exc
        if not value.strip():
            raise PromptRegistryError(f"Prompt '{prompt_id}' file {path.name} is empty")
        return value

    @staticmethod
    def _read_yaml(path: Path, prompt_id: str) -> dict[str, Any]:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise PromptRegistryError(f"Invalid metadata.yaml for prompt '{prompt_id}': {exc}") from exc
        except OSError as exc:
            raise PromptRegistryError(f"Unable to read metadata.yaml for prompt '{prompt_id}': {exc}") from exc
        if not isinstance(raw, dict):
            raise PromptRegistryError(f"metadata.yaml for prompt '{prompt_id}' must be a mapping")
        body_like_keys = {"template", "prompt", "system_prompt", "developer_prompt", "few_shots"}
        forbidden = sorted(body_like_keys.intersection(raw))
        if forbidden:
            raise PromptRegistryError(
                f"metadata.yaml for prompt '{prompt_id}' must not contain prompt body key(s): {', '.join(forbidden)}"
            )
        return raw

    @staticmethod
    def _read_json(path: Path, prompt_id: str) -> dict[str, Any]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PromptRegistryError(f"Invalid output_schema.json for prompt '{prompt_id}': {exc}") from exc
        except OSError as exc:
            raise PromptRegistryError(f"Unable to read output_schema.json for prompt '{prompt_id}': {exc}") from exc
        if not isinstance(raw, dict):
            raise PromptRegistryError(f"output_schema.json for prompt '{prompt_id}' must be a JSON object")
        return raw
