"""Shared guardrail event emission for logs and the harness audit store."""

import logging


def emit_guardrail_event(rule_type: str, detail: str, session_id: str = "") -> None:
    """Persist and log a triggered guardrail without breaking the request path."""
    try:
        from banking_agents.observability.logger import harness_logger

        harness_logger.log_guardrail_event(
            rule_type=rule_type,
            triggered=True,
            detail=detail,
            session_id=session_id,
        )
    except Exception:
        logging.exception("Failed to write guardrail event to the harness log")

    try:
        from agent_harness.audit import audit_store

        audit_store.save_guardrail_event(
            session_id=session_id,
            event_type=rule_type,
            detail=detail,
        )
    except Exception:
        logging.exception("Failed to persist guardrail event")
