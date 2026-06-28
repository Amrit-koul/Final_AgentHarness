"""
state.py: Typed state schema for the Agent Harness Parent LangGraph wrapper.

This defines the shape of the state object that flows through the parent graph
(graph.py). The graph is a thin runtime wrapper around the existing harness
orchestrator/execution path — it does not introduce new business fields.
Everything business-logic-related (payload, agent identity, result) is carried
through as opaque values so this layer never needs to know the internal shape
of chat vs. loan payloads/results.
"""

from typing import Any, Dict, Optional, TypedDict


class HarnessGraphState(TypedDict, total=False):
    # --- Inputs (set before graph.invoke) ---
    endpoint: str                      # e.g. "/api/v1/chat" or "/api/v1/loan/assess"
    agent_name: str                    # opaque application catalog/fleet identity
    session_id: str
    run_id: str
    payload: Dict[str, Any]            # opaque kwargs forwarded to AgentFleet.invoke via HarnessOrchestrator

    # Internal-only: reference to the existing HarnessOrchestrator instance so
    # execute_existing_runtime can call straight into the unchanged execution
    # path. Must be declared here (even though it's not "real" state data) --
    # LangGraph drops any key from the initial input that isn't part of the
    # schema, so omitting this would silently lose the orchestrator reference.
    # Stripped back out of the result before returning to callers in graph.py.
    _harness_orchestrator: Any

    # --- registry_check node output ---
    request_type: str                  # human-readable classification of the request
    selected_agent: Optional[str]
    agent_known: bool

    # --- runtime_control_check node output ---
    runtime_state: Optional[str]       # ACTIVE / DISABLED / UNKNOWN
    is_blocked: bool
    block_reason: Optional[str]

    # --- execute_existing_runtime node output ---
    result: Any                        # raw object returned by the existing runtime (AgentResponse or str)
    error: Optional[str]

    # --- finalize_response node output ---
    status: str                        # "success" | "blocked" | "error"
    latency_ms: int
