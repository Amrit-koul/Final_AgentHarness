"""Generic SQLite control-plane persistence implementation."""
import json
import sqlite3
import hashlib
import uuid
from pathlib import Path
from threading import Lock


class ControlPlaneStore:
    def __init__(self, path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False); self.conn.row_factory = sqlite3.Row; self.lock = Lock()
        with self.conn: self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS agents(agent_id TEXT PRIMARY KEY, name TEXT, status TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS agent_contracts(agent_id TEXT PRIMARY KEY, contract_json TEXT, source_file TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS agent_runs(trace_id TEXT PRIMARY KEY, agent_id TEXT, status TEXT, started_at TEXT, completed_at TEXT, latency_ms INTEGER, confidence REAL, input_json TEXT, output_json TEXT, error TEXT);
        CREATE TABLE IF NOT EXISTS observability_events(id INTEGER PRIMARY KEY, trace_id TEXT, agent_id TEXT, event_type TEXT, timestamp TEXT DEFAULT CURRENT_TIMESTAMP, payload_json TEXT);
        CREATE TABLE IF NOT EXISTS policy_decisions(id INTEGER PRIMARY KEY, trace_id TEXT, agent_id TEXT, action TEXT, decision TEXT, reason TEXT, timestamp TEXT DEFAULT CURRENT_TIMESTAMP, payload_json TEXT);
        CREATE TABLE IF NOT EXISTS guardrail_events(id INTEGER PRIMARY KEY, trace_id TEXT, agent_id TEXT, guardrail_id TEXT, decision TEXT, severity TEXT, reason TEXT, matched_rule TEXT, suggested_action TEXT, timestamp TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS kill_switch_events(id INTEGER PRIMARY KEY, agent_id TEXT, old_status TEXT, new_status TEXT, source TEXT, reason TEXT, triggered_by TEXT, timestamp TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS degradation_events(id INTEGER PRIMARY KEY, agent_id TEXT, source TEXT, reason TEXT, metrics_json TEXT, timestamp TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS agent_memory(agent_id TEXT, entity_id TEXT, memory_json TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(agent_id,entity_id));
        CREATE TABLE IF NOT EXISTS rag_evaluations(evaluation_id TEXT PRIMARY KEY, trace_id TEXT, agent_id TEXT, query_hash TEXT, groundedness_score REAL, semantic_similarity_score REAL, llm_judge_score REAL, answer_relevance_score REAL, citation_coverage REAL, retrieved_chunk_count INTEGER, cited_chunk_count INTEGER, evaluator_method TEXT, evaluator_prompt_id TEXT, evaluator_prompt_version TEXT, reason TEXT, metadata_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS usage_events(usage_id TEXT PRIMARY KEY, trace_id TEXT, run_id TEXT, agent_id TEXT, agent_name TEXT, business_function TEXT, provider TEXT, model TEXT, prompt_tokens INTEGER, completion_tokens INTEGER, total_tokens INTEGER, estimated_input_cost REAL, estimated_output_cost REAL, estimated_total_cost REAL, currency TEXT, pricing_source TEXT, usage_source TEXT, estimated_method TEXT, latency_ms INTEGER, retry_count INTEGER DEFAULT 0, fallback_used INTEGER DEFAULT 0, fallback_from_model TEXT, fallback_to_model TEXT, status TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, metadata_json TEXT);
        CREATE TABLE IF NOT EXISTS tool_authorization_events(id INTEGER PRIMARY KEY, timestamp TEXT, trace_id TEXT, agent_id TEXT, tool_id TEXT, action TEXT, data_scope TEXT, decision TEXT, reason TEXT, matched_policy TEXT, risk_level TEXT, required_approval INTEGER, approval_satisfied INTEGER, lifecycle_status TEXT, guardrails_evaluated TEXT, violations TEXT, runtime_enforced INTEGER, authorization_status TEXT, source TEXT, payload_summary TEXT);
        CREATE INDEX IF NOT EXISTS idx_usage_events_created_at ON usage_events(created_at);
        CREATE INDEX IF NOT EXISTS idx_usage_events_agent_id ON usage_events(agent_id);
        CREATE INDEX IF NOT EXISTS idx_usage_events_model ON usage_events(model);
        """)
        self._migrate_rag_evaluations()
        self._ensure_kill_switch_columns()
        self._ensure_tool_authorization_events_columns()
        with self.conn:
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_evaluations_trace_id ON rag_evaluations(trace_id)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_evaluations_agent_id ON rag_evaluations(agent_id)")
    def execute(self, sql, params=()):
        with self.lock, self.conn: return self.conn.execute(sql, params)
    def query(self, sql, params=()):
        with self.lock: return [dict(row) for row in self.conn.execute(sql, params).fetchall()]
    def add_event(self, event_type, trace_id, agent_id, payload): self.execute("INSERT INTO observability_events(trace_id,agent_id,event_type,payload_json) VALUES(?,?,?,?)", (trace_id, agent_id, event_type, json.dumps(payload, default=str)))
    def list_events(self, trace_id=None, limit=100): return self.query("SELECT * FROM observability_events WHERE trace_id=? ORDER BY id DESC LIMIT ?", (trace_id, limit)) if trace_id else self.query("SELECT * FROM observability_events ORDER BY id DESC LIMIT ?", (limit,))
    def start_run(self, trace_id, agent_id, payload, started_at): self.execute("INSERT INTO agent_runs(trace_id,agent_id,status,started_at,input_json) VALUES(?,?,?,?,?)", (trace_id, agent_id, "running", started_at, json.dumps(payload, default=str)))
    def finish_run(self, trace_id, status, completed_at, latency_ms, output=None, error=None, confidence=None): self.execute("UPDATE agent_runs SET status=?,completed_at=?,latency_ms=?,output_json=?,error=?,confidence=? WHERE trace_id=?", (status, completed_at, latency_ms, json.dumps(output, default=str) if output is not None else None, error, confidence, trace_id))
    def list_runs(self, trace_id=None, limit=100):
        if trace_id:
            rows = self.query("SELECT * FROM agent_runs WHERE trace_id=?", (trace_id,)); return rows[0] if rows else None
        return self.query("SELECT * FROM agent_runs ORDER BY started_at DESC LIMIT ?", (limit,))
    def _migrate_rag_evaluations(self):
        """Replace the early demo schema that persisted raw queries with a redacted schema."""
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(rag_evaluations)")}
        if not columns or "query" not in columns:
            return
        with self.lock, self.conn:
            legacy_rows = self.conn.execute("SELECT * FROM rag_evaluations").fetchall()
            self.conn.execute("ALTER TABLE rag_evaluations RENAME TO rag_evaluations_legacy")
            self.conn.execute("CREATE TABLE rag_evaluations(evaluation_id TEXT PRIMARY KEY, trace_id TEXT, agent_id TEXT, query_hash TEXT, groundedness_score REAL, semantic_similarity_score REAL, llm_judge_score REAL, answer_relevance_score REAL, citation_coverage REAL, retrieved_chunk_count INTEGER, cited_chunk_count INTEGER, evaluator_method TEXT, evaluator_prompt_id TEXT, evaluator_prompt_version TEXT, reason TEXT, metadata_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_evaluations_trace_id ON rag_evaluations(trace_id)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_evaluations_agent_id ON rag_evaluations(agent_id)")
            for row in legacy_rows:
                row = dict(row)
                metadata = json.loads(row.get("evaluation_json") or "{}")
                self.conn.execute("INSERT INTO rag_evaluations(evaluation_id,trace_id,agent_id,query_hash,groundedness_score,semantic_similarity_score,llm_judge_score,answer_relevance_score,citation_coverage,retrieved_chunk_count,cited_chunk_count,evaluator_method,evaluator_prompt_id,evaluator_prompt_version,reason,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), row.get("trace_id"), row.get("agent_id"), hashlib.sha256((row.get("query") or "").encode("utf-8")).hexdigest(), row.get("groundedness"), row.get("semantic_similarity"), row.get("llm_judge"), row.get("answer_relevance"), row.get("citation_coverage"), metadata.get("retrieved_chunk_count"), metadata.get("cited_chunk_count"), row.get("method"), metadata.get("evaluator_prompt_id"), metadata.get("evaluator_prompt_version"), row.get("reason"), json.dumps(metadata, default=str), row.get("created_at")))
            self.conn.execute("DROP TABLE rag_evaluations_legacy")
    def _ensure_kill_switch_columns(self):
        """Keep evidence fields available for databases created by earlier demos."""
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(kill_switch_events)")}
        with self.lock, self.conn:
            for name, definition in {
                "trace_id": "TEXT", "trigger": "TEXT", "severity": "TEXT", "approved_by": "TEXT", "override_type": "TEXT", "evidence_json": "TEXT",
            }.items():
                if name not in columns:
                    self.conn.execute(f"ALTER TABLE kill_switch_events ADD COLUMN {name} {definition}")
                    
    def _ensure_tool_authorization_events_columns(self):
        """Keep evidence fields available for databases created by earlier demos."""
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(tool_authorization_events)")}
        if not columns:
            return
        with self.lock, self.conn:
            for name, definition in {
                "llm_judge_status": "TEXT", "llm_judge_model": "TEXT", "llm_judge_score": "REAL", 
                "llm_judge_decision": "TEXT", "llm_judge_reasons": "TEXT", "llm_judge_prompt_version": "TEXT", 
                "llm_judge_latency_ms": "INTEGER", "llm_judge_detected_risks": "TEXT",
            }.items():
                if name not in columns:
                    self.conn.execute(f"ALTER TABLE tool_authorization_events ADD COLUMN {name} {definition}")
    def add_rag_evaluation(self, trace_id, agent_id, query, evaluation):
        query_hash = hashlib.sha256((query or "").encode("utf-8")).hexdigest()
        self.execute("INSERT INTO rag_evaluations(evaluation_id,trace_id,agent_id,query_hash,groundedness_score,semantic_similarity_score,llm_judge_score,answer_relevance_score,citation_coverage,retrieved_chunk_count,cited_chunk_count,evaluator_method,evaluator_prompt_id,evaluator_prompt_version,reason,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), trace_id, agent_id, query_hash, evaluation.get("groundedness_score"), evaluation.get("semantic_similarity_score"), evaluation.get("llm_judge_score"), evaluation.get("answer_relevance_score"), evaluation.get("citation_coverage"), evaluation.get("retrieved_chunk_count"), evaluation.get("cited_chunk_count"), evaluation.get("evaluator_method"), evaluation.get("evaluator_prompt_id"), evaluation.get("evaluator_prompt_version"), evaluation.get("reason"), json.dumps(evaluation, default=str)))
    def list_rag_evaluations(self, trace_id=None, limit=100, agent_id=None):
        clauses, params = [], []
        if trace_id: clauses.append("trace_id=?"); params.append(trace_id)
        if agent_id: clauses.append("agent_id=?"); params.append(agent_id)
        sql = "SELECT * FROM rag_evaluations" + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self.query(sql, params)
        for row in rows:
            row["rag_evaluation"] = json.loads(row.pop("metadata_json"))
        return rows

    def list_tool_authorization_events(self, limit=100, agent_id=None, decision=None, source=None):
        clauses, params = [], []
        if agent_id: clauses.append("agent_id=?"); params.append(agent_id)
        if decision: clauses.append("decision=?"); params.append(decision)
        if source: clauses.append("source=?"); params.append(source)
        sql = "SELECT * FROM tool_authorization_events" + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self.query(sql, params)
        for row in rows:
            row["required_approval"] = bool(row.get("required_approval"))
            row["approval_satisfied"] = bool(row.get("approval_satisfied"))
            row["runtime_enforced"] = bool(row.get("runtime_enforced"))
            for key in ("guardrails_evaluated", "violations", "llm_judge_reasons", "llm_judge_detected_risks"):
                value = row.get(key)
                if isinstance(value, str):
                    try:
                        row[key] = json.loads(value)
                    except json.JSONDecodeError:
                        row[key] = [] if key != "guardrails_evaluated" else value
            row["llm_judge"] = {
                "status": row.get("llm_judge_status") or "not_run",
                "model": row.get("llm_judge_model"),
                "risk_score": row.get("llm_judge_score"),
                "recommended_decision": row.get("llm_judge_decision"),
                "detected_risks": row.get("llm_judge_detected_risks") or [],
                "reasons": row.get("llm_judge_reasons") or [],
                "prompt_version": row.get("llm_judge_prompt_version"),
                "latency_ms": row.get("llm_judge_latency_ms"),
            }
        return rows
