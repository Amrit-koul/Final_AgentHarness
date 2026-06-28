import os
import uuid
import yaml
import logging
import asyncio
import threading
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from banking_agents.agents.reusable.orchestrator import OrchestratorAgent
from banking_agents.communication.message import UserQuery, AgentContext, AgentResponse, CustomerLoanProfile
from banking_agents.guardrails.input_validator import InputValidator
from banking_agents.guardrails.output_validator import OutputValidator
from banking_agents.observability.logger import harness_logger
import time
import sys
import os

# Add Backend root to sys.path to allow importing agent_harness
backend_root = os.path.dirname(os.path.dirname(__file__))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from agent_harness import HarnessOrchestrator, AgentFleet, AgentCatalog
from agent_harness.registry import agent_registry
from agent_harness.audit import audit_store
from banking_agents.harness.governance import governance_reader
from agent_harness.graph import run_harness_graph
from banking_agents.control_routes import router as control_plane_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Agentic Policy Bot Navigator",
    description="Multi-agent banking system powered by Groq",
    version="1.0.0"
)

# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Additive, YAML-driven control-plane APIs. Existing routes below remain unchanged.
app.include_router(control_plane_router)

# Load Configurations
intents_path = os.path.join(os.path.dirname(__file__), "config", "intents.yaml")
with open(intents_path, "r") as f:
    intents_data = yaml.safe_load(f)

orchestrator_path = os.path.join(os.path.dirname(__file__), "config", "orchestrator.yaml")
with open(orchestrator_path, "r") as f:
    orchestrator_data = yaml.safe_load(f)

# Load Guardrail Configuration (Constraint Handling Repository)
guardrails_path = os.path.join(os.path.dirname(__file__), "config", "guardrails.yaml")
with open(guardrails_path, "r") as f:
    guardrails_config = yaml.safe_load(f)

# Constraint Handling: Initialize Input/Output Validators
# These ensure the query is safe before processing and compliant before responding.
input_validator = InputValidator(guardrails_config["input"])
output_validator = OutputValidator(guardrails_config["output"])

# Loading the local sentence-transformer can take a while (and may download the
# model on a fresh machine). Keep that work off FastAPI's import path so Uvicorn
# can bind port 8000 immediately and the control-plane endpoints stay available.
orchestrator = None
loan_agent = None
harness_orchestrator = None
_runtime_error = None
_runtime_lock = threading.Lock()
_runtime_task = None


def _initialize_runtime():
    global orchestrator, loan_agent, harness_orchestrator, _runtime_error
    if harness_orchestrator is not None:
        return
    with _runtime_lock:
        if harness_orchestrator is not None:
            return
        try:
            runtime_orchestrator = OrchestratorAgent(
                intents_config=intents_data,
                orchestrator_config=orchestrator_data,
                guardrails_config=guardrails_config,
            )
            runtime_loan_agent = runtime_orchestrator.tool_instances["consult_loan_expert"]
            runtime_fleet = AgentFleet({
                "chat_orchestrator": lambda payload: runtime_orchestrator.run(
                    payload["user_query"], payload["context"]
                ),
                "loan_agent": lambda payload: runtime_loan_agent.answer(
                    task=payload["task"],
                    loan_profile=payload["loan_profile"],
                    session_id=payload["session_id"],
                ),
            })
            runtime_catalog = AgentCatalog({
                "chat_orchestrator": {
                    "name": "chat_orchestrator", "role": "Banking chat flow",
                    "capabilities": ["intent_classification", "rag_routing"],
                    "enabled": True, "state": "ACTIVE",
                },
                "loan_agent": {
                    "name": "loan_agent", "role": "Loan eligibility assessment",
                    "capabilities": ["structured_assessment", "rag_loan_policies"],
                    "enabled": True, "state": "ACTIVE",
                },
            })
            orchestrator = runtime_orchestrator
            loan_agent = runtime_loan_agent
            harness_orchestrator = HarnessOrchestrator(
                fleet=runtime_fleet,
                catalog=runtime_catalog,
            )
            _runtime_error = None
        except Exception as exc:
            _runtime_error = str(exc)
            logger.exception("Agent runtime initialization failed")


def _require_runtime():
    if harness_orchestrator is None:
        detail = "Agent runtime is still initializing. Please retry shortly."
        if _runtime_error:
            detail = f"Agent runtime failed to initialize: {_runtime_error}"
        raise HTTPException(status_code=503, detail=detail)
    return harness_orchestrator


@app.on_event("startup")
async def warm_agent_runtime():
    global _runtime_task
    _runtime_task = asyncio.create_task(asyncio.to_thread(_initialize_runtime))

# In-memory store for contexts (in a real app, use Redis or a database)
session_contexts = {}

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    final: str
    session_id: str
    intent: str
    audit_trail: Optional[List[Dict[str, Any]]] = None

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    try:
        runtime = _require_runtime()
        # 1. Validate Input
        input_validator.validate(request.query, session_id=session_id)

        # 2. Create or retrieve session
        if session_id not in session_contexts:
            context = AgentContext(session_id=session_id)
            session_contexts[session_id] = context
        else:
            context = session_contexts[session_id]

        user_query = UserQuery(query=request.query, session_id=session_id)
        
        # 3. Run orchestrator
        _chat_start = time.perf_counter()
        
        # HARNESS: Execute via the Parent LangGraph wrapper around the Harness
        # Orchestrator. The graph's execute_existing_runtime node calls
        # harness_orchestrator.execute(...) exactly as before; this just makes
        # that call visible as a traced parent-graph run.
        graph_result = run_harness_graph(
            endpoint="/api/v1/chat",
            agent_name="chat_orchestrator",
            session_id=session_id,
            payload={"user_query": user_query, "context": context},
            harness_orchestrator=runtime,
        )

        if graph_result["status"] == "blocked":
            raise HTTPException(status_code=503, detail=graph_result.get("block_reason") or "Chat orchestrator is currently disabled.")
        if graph_result["status"] == "error":
            # Preserve prior behavior: harness_orchestrator.execute() used to raise
            # directly and be caught by the except Exception block below.
            raise RuntimeError(graph_result.get("error") or "Unknown harness execution error")

        agent_response = graph_result["result"]
        
        _chat_ms = int((time.perf_counter() - _chat_start) * 1000)
        
        # 4. Validate and enrich output
        final_response_text = output_validator.validate(
            agent_response.final, 
            intent=agent_response.context.current_intent.value if agent_response.context.current_intent else None,
            session_id=session_id,
        )
        
        # 5. Save updated context
        session_contexts[session_id] = agent_response.context

        # HARNESS: Persist audit trail to SQLite
        audit_store.save_session(
            session_id=session_id,
            query=request.query,
            intent=agent_response.context.current_intent.value if agent_response.context.current_intent else "UNKNOWN",
            final_resp=final_response_text,
            audit_trail=agent_response.audit_trail,
            total_ms=_chat_ms,
        )
        harness_logger.log_session("session_end", session_id=session_id)
        
        return ChatResponse(
            final=final_response_text,
            session_id=session_id,
            intent=agent_response.context.current_intent.value if agent_response.context.current_intent else "UNKNOWN",
            audit_trail=agent_response.audit_trail
        )
        
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unhandled error in chat endpoint")
        raise HTTPException(status_code=500, detail="Internal server error.")

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Agentic Banking Backend is running."}


class LoanAssessRequest(BaseModel):
    session_id: Optional[str] = None
    query: str = ""            # Optional natural language context
    profile: CustomerLoanProfile

class LoanAssessResponse(BaseModel):
    session_id: str
    eligibility_assessment: str
    profile_used: CustomerLoanProfile

@app.post("/api/v1/loan/assess", response_model=LoanAssessResponse)
async def loan_assess_endpoint(request: LoanAssessRequest):
    """
    Structured loan eligibility assessment endpoint.
    Accepts a CustomerLoanProfile with validated fields and returns
    a deterministic eligibility assessment with pre-computed FOIR, LTV, etc.
    """
    try:
        runtime = _require_runtime()
        session_id = request.session_id or str(uuid.uuid4())

        if request.query:
            input_validator.validate(request.query, session_id=session_id)

        # Build the task string from the profile if no query provided
        task = request.query or (
            f"{request.profile.loan_type} loan eligibility assessment for a "
            f"{request.profile.employment_type.lower()} applicant: "
            f"monthly income ₹{request.profile.monthly_income:,.0f}, "
            f"CIBIL {request.profile.cibil_score}, "
            f"requesting ₹{request.profile.loan_amount_requested:,.0f} "
            f"for {request.profile.loan_tenure_months} months."
        )

        if not agent_registry.is_enabled("consult_loan_expert"):
            raise HTTPException(status_code=503, detail="Loan Eligibility Agent is currently disabled.")

        # Run structured assessment with pre-computed math
        started = time.perf_counter()
        
        # HARNESS: Execute via the Parent LangGraph wrapper around the Harness
        # Orchestrator. Same execution path as before, now traced as a graph run.
        graph_result = run_harness_graph(
            endpoint="/api/v1/loan/assess",
            agent_name="loan_agent",
            session_id=session_id,
            payload={"task": task, "loan_profile": request.profile, "session_id": session_id},
            harness_orchestrator=runtime,
        )

        if graph_result["status"] == "blocked":
            raise HTTPException(status_code=503, detail=graph_result.get("block_reason") or "Loan Eligibility Agent is currently disabled.")
        if graph_result["status"] == "error":
            raise RuntimeError(graph_result.get("error") or "Unknown harness execution error")

        result = graph_result["result"]
        
        latency_ms = int((time.perf_counter() - started) * 1000)
        agent_registry.record_call("consult_loan_expert", latency_ms=latency_ms, error=False)
        harness_logger.log_agent_call(
            agent="LoanEligibilityRAGAgent",
            tool="consult_loan_expert",
            latency_ms=latency_ms,
            status="success",
            session_id=session_id,
            detail=f"Structured assessment ({len(result)} chars)",
        )

        # Apply output guardrail (append LOAN_ELIGIBILITY disclaimer)
        result = output_validator.validate(
            result,
            intent="LOAN_ELIGIBILITY",
            session_id=session_id,
        )

        audit_trail = [{
            "step": 1,
            "call_type": "model",
            "agent": "LoanEligibilityRAGAgent",
            "model": loan_agent.model_id,
            "action": "Structured Loan Assessment",
            "summary": f"Completed in {latency_ms} ms",
            "output": result,
        }]
        audit_store.save_session(
            session_id=session_id,
            query=task,
            intent="LOAN_ELIGIBILITY",
            final_resp=result,
            audit_trail=audit_trail,
            total_ms=latency_ms,
        )

        return LoanAssessResponse(
            session_id=session_id,
            eligibility_assessment=result,
            profile_used=request.profile
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid loan profile: {str(e)}")
    except Exception:
        logger.exception("Unhandled error in structured loan assessment")
        if "started" in locals():
            latency_ms = int((time.perf_counter() - started) * 1000)
            agent_registry.record_call("consult_loan_expert", latency_ms=latency_ms, error=True)
        raise HTTPException(status_code=500, detail="Internal server error.")



# ═══════════════════════════════════════════════════════════════
#  AGENT HARNESS CONTROL PLANE API ENDPOINTS
# ═══════════════════════════════════════════════════════════════

class AgentToggleRequest(BaseModel):
    enabled: bool
    triggered_by: str = "dashboard"


class HarnessHealth(BaseModel):
    status: str
    components: Dict[str, str]
    agent_count: int
    total_sessions: int


@app.get("/api/v1/harness/agents")
async def get_agents():
    """Returns all agents with current status, call counts, and kill switch state."""
    return {"agents": agent_registry.get_all()}


@app.post("/api/v1/harness/agents/{agent_name}/toggle")
async def toggle_agent(agent_name: str, request: AgentToggleRequest):
    """Enable or disable an agent via the kill switch."""
    try:
        result = agent_registry.toggle(
            agent_name=agent_name,
            enabled=request.enabled,
            triggered_by=request.triggered_by,
        )
        return {"success": True, "agent": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found.")


@app.get("/api/v1/harness/audit")
async def get_audit_sessions(limit: int = 50, offset: int = 0):
    """Returns paginated list of audit sessions."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    sessions = audit_store.get_sessions(limit=limit, offset=offset)
    stats = audit_store.get_stats()
    return {"sessions": sessions, "stats": stats}


@app.get("/api/v1/harness/audit/{session_id}")
async def get_audit_session(session_id: str):
    """Returns full audit trail for a specific session."""
    session = audit_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return session


@app.get("/api/v1/harness/metrics")
async def get_metrics():
    """Returns per-agent call counts, latency, and aggregate session metrics."""
    agents = agent_registry.get_all()
    stats = audit_store.get_stats()
    agent_metrics = []
    for a in agents:
        agent_metrics.append({
            "tool_name": a["tool_name"],
            "display_name": a["display_name"],
            "calls": a["calls"],
            "errors": a["errors"],
            "avg_latency_ms": a["avg_latency_ms"],
            "enabled": a["enabled"],
        })
    return {"agents": agent_metrics, "sessions": stats}


@app.get("/api/v1/harness/governance")
async def get_governance():
    """Returns active guardrail rules and recent trigger events."""
    return governance_reader.get_governance_summary()


@app.get("/api/v1/harness/logs")
async def get_logs(n: int = 100):
    """Returns last n structured log entries from the ring buffer."""
    return {"logs": harness_logger.get_recent(n=max(1, min(n, 500)))}


@app.get("/api/v1/harness/kill-switch-log")
async def get_kill_switch_log(limit: int = 50):
    """Returns recent kill switch toggle events."""
    return {"events": agent_registry.get_kill_switch_log(limit=max(1, min(limit, 200)))}


@app.get("/api/v1/harness/health")
async def get_harness_health():
    """Returns health status of all harness components."""
    try:
        stats = audit_store.get_stats()
        agents = agent_registry.get_all()
        if harness_orchestrator is None:
            runtime_status = "failed" if _runtime_error else "initializing"
            components = {
                "agent_registry": "healthy",
                "audit_store": "healthy",
                "harness_logger": "healthy",
                "governance": "healthy",
                "agent_runtime": runtime_status,
            }
            if _runtime_error:
                components["runtime_error"] = _runtime_error
            return HarnessHealth(
                status="degraded",
                components=components,
                agent_count=len(agents),
                total_sessions=stats.get("total_sessions", 0),
            )
        policy_count = orchestrator.tool_instances["consult_policy_expert"].rag.collection.count()
        loan_count = loan_agent.rag.collection.count()
        rag_status = "healthy" if policy_count > 0 and loan_count > 0 else "empty"
        return HarnessHealth(
            status="healthy" if rag_status == "healthy" else "degraded",
            components={
                "agent_registry": "healthy",
                "audit_store": "healthy",
                "harness_logger": "healthy",
                "governance": "healthy",
                "rag_collections": f"{rag_status} (policy={policy_count}, loan={loan_count})",
            },
            agent_count=len(agents),
            total_sessions=stats.get("total_sessions", 0),
        )
    except Exception as e:
        return HarnessHealth(
            status="degraded",
            components={"error": str(e)},
            agent_count=0,
            total_sessions=0,
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("banking_agents.main:app", host="0.0.0.0", port=8000, reload=True)
