"""
observability.py: High-level observability facade for the enterprise Agent Harness control plane.
This framework module uses standard logging or an injected event sink.

This module also exposes optional LangSmith tracing for the Parent LangGraph
runtime (graph.py). LangSmith is purely additive: the local harness_logger
remains the source of truth for the existing dashboard/audit endpoints, and
LangSmith tracing is layered on top via the `langsmith` SDK's `traceable`
decorator, which is itself a safe no-op when LangSmith env vars are absent
(see `is_langsmith_enabled` / `get_langsmith_status` below).
"""

import logging
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)
LANGSMITH_PROJECT_NAME = os.environ.get("LANGSMITH_PROJECT", "aria-agent-harness-demo")


class ObservabilityHook:
    def __init__(self, event_sink=None, logger_instance=None):
        self.event_sink = event_sink
        self.logger = logger_instance or logger
        
    def emit(self, component: str, action: str, status: str, metadata: Dict[str, Any] = None):
        """
        Emit through an injected sink, falling back to standard structured logging.
        """
        event = {"component": component, "action": action, "status": status, "metadata": metadata or {}}
        if self.event_sink:
            self.event_sink(event)
        else:
            self.logger.info("harness_trace %s", event)


# ---------------------------------------------------------------------------
# LangSmith observability (additive — never replaces the local logger above)
# ---------------------------------------------------------------------------
#
# Expected env vars (read by the langsmith SDK itself, not parsed here):
#   LANGSMITH_TRACING=true
#   LANGSMITH_ENDPOINT=https://api.smith.langchain.com
#   LANGSMITH_API_KEY=<key>
#   LANGSMITH_PROJECT=aria-agent-harness-demo
#
# If these are missing, `traceable` becomes an inert pass-through decorator
# (confirmed against the installed langsmith SDK), so graph.py can apply it
# unconditionally without any if/else branching at the call site.

try:
    from langsmith import traceable as _ls_traceable
    LANGSMITH_SDK_AVAILABLE = True
except ImportError:
    LANGSMITH_SDK_AVAILABLE = False

    def _ls_traceable(*args, **kwargs):
        """Fallback no-op decorator if the langsmith package isn't installed at all."""
        def _decorator(fn):
            return fn
        # Support both @traceable and @traceable(name="...") call styles.
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return _decorator


def is_langsmith_enabled() -> bool:
    """
    Best-effort check for whether LangSmith tracing is actively configured.
    Used only for harness metadata/status reporting — never gates execution.
    The langsmith SDK independently honors LANGSMITH_TRACING itself either way.
    """
    if not LANGSMITH_SDK_AVAILABLE:
        return False
    flag = os.environ.get("LANGSMITH_TRACING", "").strip().lower()
    has_key = bool(os.environ.get("LANGSMITH_API_KEY"))
    return flag in ("true", "1", "yes") and has_key


def get_langsmith_status() -> Dict[str, Any]:
    """Lightweight status snapshot, safe to expose in harness metadata/health endpoints."""
    return {
        "sdk_available": LANGSMITH_SDK_AVAILABLE,
        "tracing_enabled": is_langsmith_enabled(),
        "project": LANGSMITH_PROJECT_NAME if is_langsmith_enabled() else None,
        "endpoint": os.environ.get("LANGSMITH_ENDPOINT") if is_langsmith_enabled() else None,
    }


def traceable_node(name: str):
    """
    Thin wrapper around langsmith.traceable for tagging individual LangGraph
    node functions. Always safe to apply: no-ops locally when LangSmith is
    not configured, and never raises even if a trace POST fails (the SDK
    swallows transport errors internally rather than breaking the run).
    """
    try:
        return _ls_traceable(name=name, run_type="chain", project_name=LANGSMITH_PROJECT_NAME)
    except TypeError:
        return _ls_traceable(name=name, run_type="chain")


# Log once at import time whether the SDK is present, purely informational.
if not LANGSMITH_SDK_AVAILABLE:
    logger.info("observability: langsmith package not installed; LangSmith tracing disabled, local observability only.")
