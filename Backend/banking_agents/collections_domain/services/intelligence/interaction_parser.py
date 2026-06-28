"""Parse interaction log strings into structured signals."""
import re
from dataclasses import dataclass
from typing import List


@dataclass
class InteractionSignals:
    voice_attempts: int = 0
    voice_pickups: int = 0
    voice_no_pickup: int = 0
    whatsapp_sent: int = 0
    whatsapp_read: int = 0
    whatsapp_not_read: int = 0
    field_visits: int = 0
    field_present: int = 0
    field_refused: int = 0
    customer_callbacks: int = 0
    ptp_secured: int = 0
    payment_attempted: int = 0
    documents_submitted: int = 0
    extension_requested: int = 0
    partial_payment: int = 0


def _lower(text: str) -> str:
    return text.lower()


def parse_interactions(interactions: List[str]) -> InteractionSignals:
    signals = InteractionSignals()

    for raw in interactions or []:
        text = _lower(raw)

        if "voice" in text:
            if "no pickup" in text or "no answer" in text or "not answered" in text:
                signals.voice_attempts += 1
                signals.voice_no_pickup += 1
            elif "ptp secured" in text or "answered" in text or "called back" in text or "pickup" in text:
                signals.voice_attempts += 1
                signals.voice_pickups += 1
            elif "customer called back" in text:
                signals.voice_attempts += 1
                signals.voice_pickups += 1
                signals.customer_callbacks += 1
            else:
                signals.voice_attempts += 1
                if "refused" not in text:
                    signals.voice_pickups += 1

        if "wa " in text or "whatsapp" in text:
            signals.whatsapp_sent += 1
            if "read" in text and "no read" not in text:
                signals.whatsapp_read += 1
            elif "no read" in text or "not read" in text:
                signals.whatsapp_not_read += 1
            elif "delivered" in text:
                signals.whatsapp_not_read += 1

        if "field visit" in text or "field" in text:
            signals.field_visits += 1
            if "present" in text or "customer present" in text:
                signals.field_present += 1
            if "refused" in text or "not discuss" in text:
                signals.field_refused += 1

        if "ptp secured" in text:
            signals.ptp_secured += 1

        if "partial payment" in text or "payment attempted" in text or "ecs" in text:
            signals.payment_attempted += 1
            signals.partial_payment += 1

        if "document" in text or "hospital" in text and "submitted" in text:
            signals.documents_submitted += 1

        if "extension" in text or "salary delayed" in text or "requesting extension" in text:
            signals.extension_requested += 1

        if re.search(r"customer called back", text):
            signals.customer_callbacks += 1

    return signals


