"""
memory.py: Shared session memory for the enterprise Agent Harness control plane.
Provides a simple, cross-agent session object store at the control-plane level.
This acts as a high-level wrapper over any internal context dictionaries,
allowing the harness to track agent invocations without interfering with internal logic.
"""

from typing import Dict, Any

class SharedMemory:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def get_session(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "session_id": session_id,
                "customer_id": None,
                "selected_agent": None,
                "context": None,
                "tool_results": [],
                "agent_outputs": [],
                "final_response": None
            }
        return self.sessions[session_id]
        
    def update_session(self, session_id: str, updates: Dict[str, Any]):
        session = self.get_session(session_id)
        session.update(updates)
