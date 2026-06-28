"""Generic injected catalog; applications own all agent definitions."""


class AgentCatalog:
    def __init__(self, agents=None): self.agents = dict(agents or {})
    def register(self, name, definition): self.agents[name] = dict(definition)
    def get_agent_info(self, name): return self.agents.get(name)
