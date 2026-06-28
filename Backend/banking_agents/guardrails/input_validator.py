import logging
from fastapi import HTTPException
from banking_agents.guardrails.events import emit_guardrail_event

logger = logging.getLogger(__name__)

class InputValidator:
    """
    Validates user input for length and potential prompt injection.
    """
    def __init__(self, config: dict):
        self.min_length = config.get("min_length", 5)
        self.max_length = config.get("max_length", 2000)
        self.injection_patterns = [p.lower() for p in config.get("injection_patterns", [])]

    def validate(self, query: str, session_id: str = "") -> None:
        """
        Runs all validation checks on the query.
        Raises HTTPException(400) if any check fails.
        """
        if not query or not query.strip():
            logger.warning("[InputValidator] Empty query received.")
            emit_guardrail_event("input.empty", "Empty query blocked", session_id)
            raise HTTPException(status_code=400, detail="Query cannot be empty.")

        query_len = len(query)
        if query_len < self.min_length:
            logger.warning("[InputValidator] Query too short: %d chars", query_len)
            emit_guardrail_event(
                "input.min_length",
                f"Query length {query_len} was below minimum {self.min_length}",
                session_id,
            )
            raise HTTPException(status_code=400, detail=f"Query is too short (min {self.min_length} chars).")
        
        if query_len > self.max_length:
            logger.warning("[InputValidator] Query too long: %d chars", query_len)
            emit_guardrail_event(
                "input.max_length",
                f"Query length {query_len} exceeded maximum {self.max_length}",
                session_id,
            )
            raise HTTPException(status_code=400, detail=f"Query is too long (max {self.max_length} chars).")

        # Scan for prompt injection
        query_lower = query.lower()
        for pattern in self.injection_patterns:
            if pattern in query_lower:
                logger.warning("[InputValidator] Prompt injection pattern detected: '%s'", pattern)
                emit_guardrail_event(
                    "input.injection_guard",
                    f"Blocked configured prompt-injection pattern: {pattern}",
                    session_id,
                )
                raise HTTPException(
                    status_code=400, 
                    detail="Your request contains prohibited instructions or patterns."
                )
        
        logger.info("[InputValidator] Input validation successful.")
