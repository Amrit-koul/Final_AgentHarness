"""Domain-neutral privacy helpers for logs, traces, and audit summaries."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit


SENSITIVE_KEYS = re.compile(
    r"(phone|mobile|email|address|pan|aadhaar|aadhar|bureau|transcript|query|input[_-]?text|output[_-]?text|context[_-]?text|user[_-]?message|answer|prompt|api[_-]?key|authorization|auth[_-]?header|password|secret|token|raw[_-]?sql|sql)",
    re.IGNORECASE,
)
ALLOWED_IDENTIFIER_KEYS = {"account_id", "customer_id", "case_id", "agent_id", "trace_id", "session_id", "prompts", "prompt_id", "prompt_name", "prompt_version", "prompt_source", "prompt_environment"}
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE = re.compile(r"(?<!\d)(?:\+?91[- ]?)?[6-9]\d{9}(?!\d)")
PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.IGNORECASE)
AADHAAR = re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")
API_KEY = re.compile(r"\b(?:sk|gsk|lsv2)_[A-Za-z0-9_-]{12,}\b")


def redact_text(value: str, max_length: int = 500) -> str:
    text = EMAIL.sub("[REDACTED_EMAIL]", str(value))
    text = PHONE.sub("[REDACTED_PHONE]", text)
    text = PAN.sub("[REDACTED_PAN]", text)
    text = AADHAAR.sub("[REDACTED_AADHAAR]", text)
    text = API_KEY.sub("[REDACTED_API_KEY]", text)
    return text if len(text) <= max_length else f"{text[:max_length]}…[TRUNCATED]"


def safe_value(value: Any, *, key: str = "", depth: int = 0) -> Any:
    """Return a bounded, JSON-safe representation with sensitive values removed."""
    if key.lower() in {"name", "customer_name", "full_name"}:
        return "[REDACTED_NAME]"
    if key and key not in ALLOWED_IDENTIFIER_KEYS and SENSITIVE_KEYS.search(key):
        return "[REDACTED]"
    if depth > 4:
        return "[MAX_DEPTH]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if key.lower() in {"url", "endpoint", "uri"}:
            try:
                parts = urlsplit(value)
                value = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
            except ValueError:
                value = "[REDACTED_URL]"
        return redact_text(value)
    if isinstance(value, dict):
        return {str(k): safe_value(v, key=str(k), depth=depth + 1) for k, v in list(value.items())[:50]}
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        return [safe_value(item, depth=depth + 1) for item in items[:25]] + ([f"[{len(items) - 25} MORE]"] if len(items) > 25 else [])
    return redact_text(str(value))


def safe_summary(payload: Any) -> dict:
    safe = safe_value(payload)
    if isinstance(safe, dict):
        return safe
    return {"value": safe}


def contract_summary(contract: Any) -> dict:
    return {
        "agent_id": contract.agent_id,
        "agent_name": contract.name,
        "business_function": contract.business_function,
        "adapter_type": contract.adapter_type,
        "execution_mode": contract.execution_mode,
        "status": contract.status.value,
        "manifest_source_file": contract.metadata.get("source_file", ""),
        "version": contract.version,
        "tools": list(contract.tools),
        "guardrails": list(contract.guardrails),
        "prompts": list(contract.prompts),
    }
