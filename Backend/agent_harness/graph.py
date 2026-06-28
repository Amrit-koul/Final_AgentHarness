"""
graph.py: Minimal Parent LangGraph runtime wrapper for the enterprise Agent
Harness control plane.

This module makes the existing Agent Harness execution path (catalog lookup ->
runtime control check -> AgentFleet.invoke, all already implemented in
orchestrator.py/control.py/catalog.py) visible as an explicit parent runtime
graph, and traceable in LangSmith.

It is intentionally a thin wrapper:

    START
      -> registry_check            (identify endpoint / selected agent)
      -> runtime_control_check     (read current ACTIVE/DISABLED state)
      -> execute_existing_runtime  (delegate to HarnessOrchestrator.execute,
                                     i.e. the existing, unchanged execution path)
      -> finalize_response         (preserve response shape, emit final trace)
      -> END

No business logic, prompts, RAG, or response schemas are touched here. The
`execute_existing_runtime` node calls straight into the pre-existing
`HarnessOrchestrator.execute(...)`. This graph only adds visibility around the
same injected application call.

Usage from an application entrypoint:

    from agent_harness.graph import run_harness_graph

    result_state = run_harness_graph(
        endpoint="/api/v1/chat",
        agent_name="configured_agent",
        session_id=session_id,
        payload={"user_query": user_query, "context": context},
        harness_orchestrator=harness_orchestrator,
    )

    if result_state["status"] == "blocked":
        # handle disabled-agent case
        ...
    agent_response = result_state["result"]  # same object the old direct call returned
"""

import logging
import time
import uuid
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, START, END

from .state import HarnessGraphState
from .observability import ObservabilityHook, traceable_node, is_langsmith_enabled
from .control import RuntimeControl

logger = logging.getLogger(__name__)

_observability = ObservabilityHook()


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------
#
# Note: registry_check / runtime_control_check below perform the SAME catalog
# lookup and ACTIVE/DISABLED check that HarnessOrchestrator.execute() already
# performs internally. They are intentionally read-only / advisory here: their
# job is to make these steps visible as distinct graph nodes in the trace.
# The actual enforcement (raising on disabled agents) still happens exactly
# once, inside execute_existing_runtime, via the existing unchanged
# HarnessOrchestrator.execute() call -- so behavior cannot diverge from the
# pre-graph code path.

@traceable_node("registry_check")
def registry_check(state: HarnessGraphState) -> HarnessGraphState:
    endpoint = state.get("endpoint", "unknown")
    agent_name = state.get("agent_name")

    runtime = state.get("_harness_orchestrator")
    agent_info = runtime.catalog.get_agent_info(agent_name) if runtime and agent_name else None
    selected_agent = agent_info["name"] if agent_info else None

    _observability.emit(
        "ParentGraph", "registry_check", "SUCCESS",
        {
            "endpoint": endpoint,
            "agent_name": agent_name,
            "agent_known": agent_info is not None,
            "session_id": state.get("session_id"),
            "run_id": state.get("run_id"),
        },
    )

    return {
        "request_type": endpoint,
        "selected_agent": selected_agent,
        "agent_known": agent_info is not None,
    }


@traceable_node("runtime_control_check")
def runtime_control_check(state: HarnessGraphState) -> HarnessGraphState:
    agent_name = state.get("agent_name")
    runtime = state.get("_harness_orchestrator")
    agent_info = runtime.catalog.get_agent_info(agent_name) if runtime and agent_name else None

    if agent_info is None:
        # Unknown agent — let execute_existing_runtime raise the same
        # ValueError HarnessOrchestrator.execute() already raises for this case.
        runtime_state = "UNKNOWN"
        is_blocked = False
        block_reason = None
    else:
        active = RuntimeControl.is_active(agent_info["state"], agent_name=agent_name)
        enabled = agent_info["enabled"]
        runtime_state = agent_info["state"] if (active and enabled) else "DISABLED"
        is_blocked = not (active and enabled)
        block_reason = f"Agent '{agent_name}' is DISABLED" if is_blocked else None

    _observability.emit(
        "ParentGraph", "runtime_control_check", "BLOCKED" if is_blocked else "SUCCESS",
        {
            "agent_name": agent_name,
            "runtime_state": runtime_state,
            "session_id": state.get("session_id"),
            "run_id": state.get("run_id"),
        },
    )

    return {
        "runtime_state": runtime_state,
        "is_blocked": is_blocked,
        "block_reason": block_reason,
    }


@traceable_node("execute_existing_runtime")
def execute_existing_runtime(state: HarnessGraphState) -> HarnessGraphState:
    """
    Delegates to the existing, unchanged HarnessOrchestrator.execute(...) path.
    This is the ONLY place business logic is invoked. No duplication of
    catalog/control logic happens here -- HarnessOrchestrator.execute already
    re-validates catalog + runtime control internally and raises on its own
    for disabled/unknown agents, exactly as it did before this graph existed.
    """
    harness_orchestrator = state.get("_harness_orchestrator")
    session_id = state.get("session_id")
    agent_name = state.get("agent_name")
    payload = state.get("payload", {})

    if state.get("is_blocked"):
        # Short-circuit without calling business logic, but keep this as an
        # explicit node outcome so the trace shows where execution stopped.
        _observability.emit(
            "ParentGraph", "execute_existing_runtime", "BLOCKED",
            {"agent_name": agent_name, "session_id": session_id, "run_id": state.get("run_id")},
        )
        return {"result": None, "error": state.get("block_reason")}

    try:
        result = harness_orchestrator.execute(
            session_id=session_id,
            agent_name=agent_name,
            payload=payload,
        )
        _observability.emit(
            "ParentGraph", "execute_existing_runtime", "SUCCESS",
            {"agent_name": agent_name, "session_id": session_id, "run_id": state.get("run_id")},
        )
        return {"result": result, "error": None}
    except Exception as e:
        _observability.emit(
            "ParentGraph", "execute_existing_runtime", "ERROR",
            {"agent_name": agent_name, "session_id": session_id, "run_id": state.get("run_id"), "error": str(e)},
        )
        return {"result": None, "error": str(e)}


@traceable_node("finalize_response")
def finalize_response(state: HarnessGraphState) -> HarnessGraphState:
    if state.get("is_blocked"):
        status = "blocked"
    elif state.get("error"):
        status = "error"
    else:
        status = "success"

    _observability.emit(
        "ParentGraph", "finalize_response", "SUCCESS",
        {
            "endpoint": state.get("endpoint"),
            "agent_name": state.get("agent_name"),
            "session_id": state.get("session_id"),
            "run_id": state.get("run_id"),
            "status": status,
        },
    )

    return {"status": status}


# ---------------------------------------------------------------------------
# Graph assembly (built once at import time, like the existing singletons in
# this package — catalog, registry, audit_store, governance_reader)
# ---------------------------------------------------------------------------

def _build_graph():
    builder = StateGraph(HarnessGraphState)

    builder.add_node("registry_check", registry_check)
    builder.add_node("runtime_control_check", runtime_control_check)
    builder.add_node("execute_existing_runtime", execute_existing_runtime)
    builder.add_node("finalize_response", finalize_response)

    builder.add_edge(START, "registry_check")
    builder.add_edge("registry_check", "runtime_control_check")
    builder.add_edge("runtime_control_check", "execute_existing_runtime")
    builder.add_edge("execute_existing_runtime", "finalize_response")
    builder.add_edge("finalize_response", END)

    return builder.compile()


_parent_graph = _build_graph()


# ---------------------------------------------------------------------------
# Public entrypoint used by application runtimes
# ---------------------------------------------------------------------------

def run_harness_graph(
    endpoint: str,
    agent_name: str,
    session_id: str,
    payload: Dict[str, Any],
    harness_orchestrator,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Runs the parent harness graph for a single request and returns the final
    state dict. Callers should check `result["status"]`:

      - "success" -> use result["result"] exactly as the old direct
                      harness_orchestrator.execute(...) return value
      - "blocked" -> agent is disabled; result["block_reason"] has detail
      - "error"   -> result["error"] has the exception message; callers
                      should raise/handle exactly as they did when
                      harness_orchestrator.execute() raised directly before

    Every invocation is wrapped in a LangSmith trace named
    "Agent Harness Run - <endpoint>" when LangSmith is configured; otherwise
    this runs purely locally with no behavior change and no network calls.
    """
    run_id = run_id or str(uuid.uuid4())
    started = time.perf_counter()

    initial_state: HarnessGraphState = {
        "endpoint": endpoint,
        "agent_name": agent_name,
        "session_id": session_id,
        "run_id": run_id,
        "payload": payload,
        "_harness_orchestrator": harness_orchestrator,
    }

    traced_invoke = traceable_node(f"Agent Harness Run - {endpoint}")(_invoke_graph)
    final_state = traced_invoke(initial_state)

    final_state["latency_ms"] = int((time.perf_counter() - started) * 1000)
    # Strip the internal-only orchestrator reference before returning to callers.
    final_state.pop("_harness_orchestrator", None)

    if final_state.get("status") == "error":
        logger.warning(
            "run_harness_graph: endpoint=%s agent=%s run_id=%s ended in error: %s",
            endpoint, agent_name, run_id, final_state.get("error"),
        )

    return final_state


def _invoke_graph(initial_state: HarnessGraphState) -> Dict[str, Any]:
    """Separated so it can be wrapped by traceable_node with a per-request name."""
    config = {
        "run_name": f"Agent Harness Run - {initial_state.get('endpoint')}",
        "metadata": {
            "session_id": initial_state.get("session_id"),
            "run_id": initial_state.get("run_id"),
            "endpoint": initial_state.get("endpoint"),
            "selected_agent": initial_state.get("agent_name"),
            "langsmith_enabled": is_langsmith_enabled(),
        },
        "tags": ["agent-harness", "parent-graph"],
    }
    return _parent_graph.invoke(initial_state, config=config)
