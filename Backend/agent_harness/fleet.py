"""Generic injected execution mapping."""


class AgentFleet:
    def __init__(self, handlers=None, **legacy_instances):
        self.handlers = dict(handlers or {})
        # Compatibility: applications can still inject named instances, but dispatch is registered externally.
        self.instances = legacy_instances
    def register(self, name, handler): self.handlers[name] = handler
    def invoke(self, name, payload):
        if name not in self.handlers: raise ValueError(f"Unknown agent in fleet: {name}")
        return self.handlers[name](payload)
