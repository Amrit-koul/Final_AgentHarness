"""Compatibility shim; bank policy composition lives in banking_agents.policy."""
from agent_harness.policy import PolicyDecision
from banking_agents.policy.control_plane import BankPolicyEngine
PolicyEngine = BankPolicyEngine
