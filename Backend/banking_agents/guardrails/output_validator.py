import logging
from banking_agents.guardrails.events import emit_guardrail_event

logger = logging.getLogger(__name__)

class OutputValidator:
    """
    Validates and enriches the final agent output.
    """
    def __init__(self, config: dict):
        self.fallback = config.get("empty_response_fallback", "I'm sorry, I couldn't generate a response.")
        self.intent_disclaimers = config.get("intent_disclaimers", {})

    def validate(self, response: str, intent: str | None = None, session_id: str = "") -> str:
        """
        Ensures response is not empty and appends intent-specific disclaimers.
        """
        if not response or not response.strip():
            logger.warning("[OutputValidator] Empty response detected. Using fallback.")
            emit_guardrail_event("output.empty_response", "Empty agent response replaced with fallback", session_id)
            return self.fallback

        # Append disclaimer if intent matches
        if intent and intent in self.intent_disclaimers:
            disclaimer = self.intent_disclaimers[intent]
            logger.info("[OutputValidator] Appending disclaimer for intent: %s", intent)
            # Avoid duplicate disclaimer if already present
            if disclaimer not in response:
                emit_guardrail_event(
                    f"output.disclaimer.{intent}",
                    f"Mandatory {intent} disclaimer appended",
                    session_id,
                )
                response = f"{response.strip()}\n\n{disclaimer}"

        return response
