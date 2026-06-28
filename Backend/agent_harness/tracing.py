"""Optional LangSmith tracing with nested spans and a no-op fallback."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import os
from typing import Any, Iterator

from .redaction import safe_summary


def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


class TraceSpan:
    def __init__(self, run=None):
        self.run = run
        self.outputs: dict | None = None

    def set_output(self, output: Any) -> None:
        self.outputs = safe_summary(output)

    def add_metadata(self, metadata: dict) -> None:
        if self.run is not None:
            self.run.add_metadata(safe_summary(metadata))

    def add_tags(self, tags: list[str]) -> None:
        if self.run is not None:
            self.run.add_tags([str(tag) for tag in tags if tag])


_ACTIVE_RUN = ContextVar("agent_harness_active_langsmith_run", default=None)
_PROJECT_NAME = "aria-agent-harness-demo"


class TraceManager:
    def __init__(self, project_name: str | None = None):
        # Keep demo traces in one stable project; do not honor stale local env
        # values that would split traces across older project names.
        self.project_name = _PROJECT_NAME

    @property
    def enabled(self) -> bool:
        tracing = _truthy("LANGCHAIN_TRACING_V2") or _truthy("LANGSMITH_TRACING")
        return tracing and bool(os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY"))

    @contextmanager
    def trace(
        self,
        name: str,
        *,
        inputs: Any = None,
        metadata: dict | None = None,
        tags: list[str] | None = None,
        run_type: str = "chain",
    ) -> Iterator[TraceSpan]:
        """Create a top-level trace for one external/API invocation.

        Internal code should call ``span`` instead. Root traces explicitly ignore
        any ambient LangSmith context so a demo request cannot become a child of
        a leftover validation/test run.
        """
        if not self.enabled:
            yield TraceSpan()
            return
        try:
            from langsmith.run_helpers import trace as langsmith_trace
            context = langsmith_trace(name, run_type=run_type, inputs=safe_summary(inputs or {}), metadata=safe_summary(metadata or {}), tags=[str(tag) for tag in (tags or []) if tag], project_name=self.project_name, parent="ignore")
            run = context.__enter__()
        except Exception:
            yield TraceSpan()
            return
        span = TraceSpan(run)
        token = _ACTIVE_RUN.set(run)
        try:
            yield span
        except BaseException as exc:
            try: context.__exit__(type(exc), exc, exc.__traceback__)
            except Exception: pass
            raise
        else:
            try:
                if span.outputs is not None: run.end(outputs=span.outputs)
                context.__exit__(None, None, None)
            except Exception:
                pass
        finally:
            _ACTIVE_RUN.reset(token)

    @contextmanager
    def span(
        self,
        name: str,
        *,
        inputs: Any = None,
        metadata: dict | None = None,
        tags: list[str] | None = None,
        run_type: str = "chain",
    ) -> Iterator[TraceSpan]:
        """Create a child span under the active root/parent run.

        If no active root exists, this intentionally becomes a no-op instead of
        creating an independent LangSmith root trace. That keeps prompt loading,
        prompt rendering, adapter calls, and business spans from appearing as
        separate top-level rows.
        """
        parent = _ACTIVE_RUN.get()
        if not self.enabled or parent is None:
            yield TraceSpan()
            return
        try:
            from langsmith.run_helpers import trace as langsmith_trace
            context = langsmith_trace(name, run_type=run_type, inputs=safe_summary(inputs or {}), metadata=safe_summary(metadata or {}), tags=[str(tag) for tag in (tags or []) if tag], project_name=self.project_name, parent=parent)
            run = context.__enter__()
        except Exception:
            yield TraceSpan()
            return
        child = TraceSpan(run)
        token = _ACTIVE_RUN.set(run)
        try:
            yield child
        except BaseException as exc:
            try: context.__exit__(type(exc), exc, exc.__traceback__)
            except Exception: pass
            raise
        else:
            try:
                if child.outputs is not None: run.end(outputs=child.outputs)
                context.__exit__(None, None, None)
            except Exception:
                pass
        finally:
            _ACTIVE_RUN.reset(token)


_TRACER = TraceManager()


def get_tracer() -> TraceManager:
    return _TRACER
