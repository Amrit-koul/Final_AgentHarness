"""
orchestrator.py: Harness Orchestrator entrypoint for the enterprise Agent Harness control plane.
This acts as the unified execution facade. It receives requests, resolves
agent identity via the catalog, enforces runtime states via control checks,
maintains session memory, and coordinates tracing via the observability hook,
before finally delegating deep business logic execution to the Agent Fleet.
"""

from typing import Any, Dict
from .catalog import AgentCatalog
from .control import RuntimeControl
from .memory import SharedMemory
from .observability import ObservabilityHook
from .fleet import AgentFleet

class HarnessOrchestrator:
    def __init__(self, fleet: AgentFleet, catalog: AgentCatalog = None, observability=None):
        self.catalog = catalog or AgentCatalog()
        self.memory = SharedMemory()
        self.observability = observability or ObservabilityHook()
        self.fleet = fleet

    def execute(self, session_id: str, agent_name: str, payload: Dict[str, Any]) -> Any:
        self.observability.emit("HarnessOrchestrator", "receive_request", "START", {"session_id": session_id, "agent": agent_name})
        
        # Load catalog
        agent_info = self.catalog.get_agent_info(agent_name)
        if not agent_info:
            self.observability.emit("HarnessOrchestrator", "select_agent", "ERROR", {"error": "Agent not found"})
            raise ValueError(f"Agent {agent_name} not found in catalog")
        
        # Check runtime control
        if not RuntimeControl.is_active(agent_info["state"], agent_name=agent_name) or not agent_info["enabled"]:
            self.observability.emit("HarnessOrchestrator", "runtime_control", "BLOCKED", {"agent": agent_name})
            raise RuntimeError(f"Agent {agent_name} is DISABLED")

        # Select agent and prepare memory
        self.memory.update_session(session_id, {"selected_agent": agent_name})
        
        # Invoke Fleet
        self.observability.emit("HarnessOrchestrator", "invoke_fleet", "START", {"agent": agent_name})
        try:
            result = self.fleet.invoke(agent_name, payload)
            
            # Collect output
            self.memory.update_session(session_id, {
                "agent_outputs": [result],
                "final_response": result
            })
            
            self.observability.emit("HarnessOrchestrator", "invoke_fleet", "SUCCESS", {"agent": agent_name})
            return result
        except Exception as e:
            self.observability.emit("HarnessOrchestrator", "invoke_fleet", "ERROR", {"agent": agent_name, "error": str(e)})
            raise
