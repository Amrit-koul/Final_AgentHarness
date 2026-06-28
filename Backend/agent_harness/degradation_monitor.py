"""Generic rolling health evaluator with injected lifecycle service."""
import json


RAG_AGENT_IDS = {"policy_assistant_agent", "loan_assessment_agent"}

class DegradationMonitor:
    def __init__(self, registry, store, kill_switch, rules=None): self.registry, self.store, self.kill_switch, self.rules = registry, store, kill_switch, rules or {}
    def _rules(self, agent_id):
        base = {**self.rules.get("default", {})}; specific = self.rules.get(agent_id, {})
        base.update({key: value for key, value in specific.items() if key != "rag"}); base["rag"] = {**self.rules.get("rag", {}), **specific.get("rag", {})}; return base
    def evaluate(self, agent_id, trace_id=None):
        metrics = self.registry.metrics(agent_id); recent = metrics["recent"]; rules = self._rules(agent_id)
        window = recent[-rules.get("failure_window", 5):]; failures = sum(not run["success"] for run in window)
        confidences = [run["confidence"] for run in window if run["confidence"] is not None]; latencies = [run["latency_ms"] for run in window if run["latency_ms"] is not None]
        reason = None
        if failures >= rules.get("failure_threshold", 3): reason = "high_failure_rate"
        elif confidences and len(confidences) >= min(3, len(window)) and sum(confidences) / len(confidences) < rules.get("min_confidence", .5): reason = "low_confidence"
        elif latencies and len(latencies) >= min(3, len(window)) and sum(latencies) / len(latencies) > rules.get("max_avg_latency_ms", 8000): reason = "high_latency"
        elif metrics["policy_blocks"] >= rules.get("policy_block_threshold", 3): reason = "repeated_policy_blocks"
        rag = self.store.query("SELECT * FROM rag_evaluations WHERE agent_id=? ORDER BY created_at DESC LIMIT 1", (agent_id,)) if agent_id in RAG_AGENT_IDS else []
        if not reason and rag:
            sample, rag_rules = rag[0], rules["rag"]
            metadata = json.loads(sample.get("metadata_json") or "{}")
            source = metadata.get("source") or metadata.get("evaluation_source") or "runtime"
            if metadata.get("is_simulated") or source != "runtime":
                sample = None
        if not reason and rag and sample:
            checks = [("groundedness_score", "min_groundedness"), ("semantic_similarity_score", "min_semantic_similarity"), ("citation_coverage", "min_citation_coverage"), ("llm_judge_score", "min_llm_judge_score"), ("answer_relevance_score", "min_answer_relevance")]
            if any(sample.get(score) is not None and threshold in rag_rules and sample[score] < rag_rules[threshold] for score, threshold in checks): reason = "rag_quality_degradation"
        if not reason or self.registry.get_contract(agent_id).status.value == "review": return None
        evidence = {"metrics": metrics, "rules": rules, "latest_rag_evaluation": rag[0] if rag else None}
        self.store.execute("INSERT INTO degradation_events(agent_id,source,reason,metrics_json) VALUES(?,?,?,?)", (agent_id, "automatic", reason, json.dumps(evidence, default=str)))
        action = self.rules.get("actions", {}).get("on_quality_degradation", "review")
        return self.kill_switch.change_status(agent_id, action, "automatic", reason, trace_id=trace_id, severity="MEDIUM", evidence=evidence)
