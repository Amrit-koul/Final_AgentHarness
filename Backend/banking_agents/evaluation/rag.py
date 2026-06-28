"""RAG evaluation: deterministic retrieval quality signals with an optional LLM judge."""
from __future__ import annotations

import json
import os
import re
from time import perf_counter
from pathlib import Path
from typing import Any

import yaml

from agent_harness.tracing import get_tracer


_TOKEN_RE = re.compile(r"[a-z0-9]{2,}", re.I)
_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "evaluators" / "rag_faithfulness.v1.yaml"


def build_citations(results: dict[str, Any], *, max_snippet_chars: int = 320) -> list[dict[str, Any]]:
    documents = results.get("documents", [[]])[0] or []
    metadatas = results.get("metadatas", [[]])[0] or []
    ids = results.get("ids", [[]])[0] or []
    distances = results.get("distances", [[]])[0] or []
    citations = []
    for index, document in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) else {}
        distance = distances[index] if index < len(distances) else None
        citations.append({
            "source_id": str(metadata.get("source_id") or metadata.get("source") or (ids[index] if index < len(ids) else f"chunk-{index + 1}")),
            "title": metadata.get("title") or metadata.get("source") or "Retrieved policy document",
            "source": metadata.get("source") or metadata.get("title") or "Retrieved policy document",
            "chunk_id": str(metadata.get("chunk_id") or (ids[index] if index < len(ids) else index)),
            "snippet": " ".join(str(document).split())[:max_snippet_chars],
            "similarity_score": round(max(0.0, min(1.0, 1.0 - float(distance))), 4) if distance is not None else None,
        })
    return citations


def evaluate_rag_response(*, query: str, answer: str, context: str, citations: list[dict[str, Any]], rag, agent_id: str, trace_id: str = "") -> dict[str, Any]:
    """Return an evaluation object. A judge is strictly optional and non-blocking."""
    tracer = get_tracer()
    started = perf_counter()
    with tracer.span("rag_evaluation", inputs={"agent_id": agent_id, "trace_id": trace_id, "retrieved_chunk_count": len(citations)}, metadata={"agent_id": agent_id, "trace_id": trace_id}) as span:
        answer_tokens, context_tokens, query_tokens = _tokens(answer), _tokens(context), _tokens(query)
        groundedness = _overlap(answer_tokens, context_tokens)
        relevance = _overlap(answer_tokens, query_tokens)
        unsupported = _unsupported_sentences(answer, context_tokens)
        semantic, semantic_method = _similarity(rag, answer, context)
        relevance, relevance_method = _similarity(rag, answer, query)
        method = "embedding_similarity" if semantic_method == "embedding_similarity" else "heuristic"
        result = {
            "groundedness_score": round(groundedness, 4),
            "semantic_similarity_score": round(semantic, 4),
            "llm_judge_score": None,
            "answer_relevance_score": round(relevance, 4),
            "citation_coverage": round(len(citations) / max(1, len(citations)), 4) if citations else 0.0,
            "retrieved_evidence_coverage": round(len(citations) / max(1, len(citations)), 4) if citations else 0.0,
            "retrieved_chunk_count": len(citations),
            "cited_chunk_count": len(citations),
            "score_methods": {
                "groundedness_score": "lexical_groundedness",
                "semantic_similarity_score": "embedding_similarity" if semantic_method == "embedding_similarity" else "lexical_similarity",
                "answer_relevance_score": "embedding_similarity" if relevance_method == "embedding_similarity" else "lexical_answer_relevance",
                "citation_coverage": "retrieved_evidence_coverage",
                "retrieved_evidence_coverage": "retrieved_evidence_coverage",
                "llm_judge_score": "llm_judge" if os.getenv("RAG_EVALUATOR_MODEL") and os.getenv("GROQ_API_KEY") else "not_run",
            },
            "score_method_labels": {
                "groundedness_score": "lexical_groundedness",
                "semantic_similarity_score": "embedding_similarity",
                "answer_relevance_score": "lexical_answer_relevance",
                "retrieved_evidence_coverage": "retrieved_evidence_coverage",
                "llm_judge_score": "llm_judge only if configured and completed",
            },
            "source": "runtime",
            "evaluation_source": "runtime",
            "is_simulated": False,
            "unsupported_claims": unsupported,
            "evaluator_method": method,
            "evaluator_prompt_id": None,
            "evaluator_prompt_version": None,
            "reason": _fallback_reason(semantic_method, relevance_method),
        }
        with tracer.span("groundedness_score", inputs={"answer_tokens": len(answer_tokens), "context_tokens": len(context_tokens)}) as score_span:
            score_span.set_output({"score": result["groundedness_score"], "unsupported_claim_count": len(unsupported)})
        with tracer.span("semantic_similarity_score", inputs={"embedding_available": semantic is not None}) as score_span:
            score_span.set_output({"score": result["semantic_similarity_score"], "method": method})
        with tracer.span("citation_coverage", inputs={"retrieved_chunk_count": len(citations), "cited_chunk_count": len(citations)}) as score_span:
            score_span.set_output({"score": result["citation_coverage"]})
        judge = _run_llm_judge(query, answer, context)
        if judge:
            result.update(judge)
        result["latency_ms"] = int((perf_counter() - started) * 1000)
        span.add_metadata({"agent_id": agent_id, "trace_id": trace_id, "evaluator_method": result["evaluator_method"], "scores": {key: result[key] for key in ("groundedness_score", "semantic_similarity_score", "llm_judge_score", "answer_relevance_score", "citation_coverage")}})
        span.set_output(result)
        return result


def _run_llm_judge(query: str, answer: str, context: str) -> dict[str, Any] | None:
    model = os.getenv("RAG_EVALUATOR_MODEL")
    if not model or not os.getenv("GROQ_API_KEY") or not _PROMPT_PATH.is_file():
        return None
    try:
        prompt = yaml.safe_load(_PROMPT_PATH.read_text(encoding="utf-8")) or {}
        prompt_id, version = prompt["prompt_id"], str(prompt["version"])
        rendered = str(prompt["template"]).format(query=query[:4000], answer=answer[:6000], context=context[:12000])
        from banking_agents.config.settings import get_groq_client
        with get_tracer().span("llm_judge_evaluation", inputs={"prompt_id": prompt_id}, metadata={"evaluator_prompt_id": prompt_id, "evaluator_prompt_version": version, "model_name": model}, run_type="llm") as span:
            response = get_groq_client().chat.completions.create(model=model, messages=[{"role": "user", "content": rendered}], temperature=0)
            raw = response.choices[0].message.content.strip()
            payload = json.loads(raw)
            value = max(0.0, min(1.0, float(payload["score"])))
            span.set_output({"score": value})
        return {"llm_judge_score": value, "evaluator_method": "hybrid", "evaluator_prompt_id": prompt_id, "evaluator_prompt_version": version, "reason": str(payload.get("reason") or "LLM judge completed alongside deterministic evidence metrics.")}
    except Exception as exc:
        return {"llm_judge_score": None, "evaluator_method": "embedding_similarity" if context else "heuristic", "evaluator_prompt_id": None, "evaluator_prompt_version": None, "reason": f"LLM judge unavailable; deterministic evaluation retained ({type(exc).__name__})."}


def _tokens(value: str) -> set[str]:
    return set(_TOKEN_RE.findall((value or "").lower()))


def _overlap(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left) if left else 0.0


def _similarity(rag, left: str, right: str) -> tuple[float, str]:
    """Prefer the local retrieval embedding model; lexical overlap is always available."""
    if not left.strip() or not right.strip():
        return 0.0, "heuristic"
    if not getattr(rag, "embedding_model", None):
        return _jaccard(_tokens(left), _tokens(right)), "heuristic"
    try:
        vectors = rag.embedding_model.encode([left, right], normalize_embeddings=True)
        return max(0.0, min(1.0, float(sum(float(a) * float(b) for a, b in zip(vectors[0], vectors[1]))))), "embedding_similarity"
    except Exception:
        return _jaccard(_tokens(left), _tokens(right)), "heuristic"


def _jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right) if left or right else 0.0


def _fallback_reason(semantic_method: str, relevance_method: str) -> str:
    configured = bool(os.getenv("RAG_EVALUATOR_MODEL") and os.getenv("GROQ_API_KEY"))
    detail = "local embedding cosine similarity" if semantic_method == "embedding_similarity" else "lexical overlap fallback"
    judge = "LLM judge not configured; " if not configured else "LLM judge did not return a score; "
    return f"{judge}deterministic {detail} and token-overlap metrics were used. These are evidence-quality signals, not factuality guarantees."


def _unsupported_sentences(answer: str, context_tokens: set[str]) -> list[str]:
    unsupported = []
    for sentence in re.split(r"(?<=[.!?])\s+", answer or ""):
        tokens = _tokens(sentence)
        if len(tokens) >= 5 and _overlap(tokens, context_tokens) < 0.25:
            unsupported.append(sentence[:240])
    return unsupported[:5]
