"""
control.py: Runtime control facade for the enterprise Agent Harness control plane.
This enforces basic state checks before allowing execution, delegating to the 
injected application registry to evaluate if an agent is enabled.
"""

from .registry import agent_registry

class RuntimeControl:
    @staticmethod
    def is_active(state: str, agent_name: str = None) -> bool:
        """
        Check if an agent is active.
        If agent_name is provided, delegates to the internal registry kill switch.
        """
        if state != "ACTIVE":
            return False
            
        if agent_name:
            return agent_registry.is_enabled(agent_name)
            
        return True
