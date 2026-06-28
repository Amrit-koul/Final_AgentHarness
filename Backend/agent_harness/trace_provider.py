from abc import ABC, abstractmethod

class TraceProvider(ABC):
    @abstractmethod
    def emit(self, event_type, trace_id, agent_id, payload): ...
class LocalTraceProvider(TraceProvider):
    def __init__(self, store): self.store = store
    def emit(self, event_type, trace_id, agent_id, payload): self.store.add_event(event_type, trace_id, agent_id, payload)
class LangSmithTraceProvider(TraceProvider):
    """Persists local events; structured LangSmith spans are managed by TraceManager."""
    def __init__(self, fallback, tracer=None):
        from .tracing import get_tracer
        self.fallback, self.tracer = fallback, tracer or get_tracer()
    def emit(self, event_type, trace_id, agent_id, payload):
        self.fallback.emit(event_type, trace_id, agent_id, payload)
