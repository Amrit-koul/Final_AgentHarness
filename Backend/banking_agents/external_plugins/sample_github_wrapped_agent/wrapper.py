"""Controlled boundary around a reviewed, vendored repository agent."""

from .vendor_src.repo_agent import run


def invoke(payload, trace_id=""):
    """Translate the vendored implementation into the public agent contract."""
    try:
        query = payload.get("query") if isinstance(payload, dict) else None
        return {
            "status": "success",
            "result": run(query),
            "source": "github_wrapped_plugin",
            "trace_id": trace_id,
        }
    except Exception as exc:
        return {
            "status": "error",
            "result": "The wrapped vendor agent could not process this request.",
            "source": "github_wrapped_plugin",
            "trace_id": trace_id,
            "error": str(exc),
        }
