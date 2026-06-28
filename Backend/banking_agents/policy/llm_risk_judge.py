import json
import logging
import os
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Dict, Any, List
import requests
import yaml

logger = logging.getLogger(__name__)

@dataclass
class LLMRiskJudgeRequest:
    task_type: str
    agent_id: str
    tool_id: str
    action: str
    payload_summary: str
    candidate_output: Optional[str] = None
    retrieved_context: Optional[str] = None
    policy_context: Optional[str] = None
    risk_context: Optional[dict] = field(default_factory=dict)
    trace_id: Optional[str] = None

@dataclass
class LLMRiskJudgeResponse:
    judge_status: str  # not_configured | not_run | success | error | timeout | invalid_response
    model: Optional[str] = None
    task_type: Optional[str] = None
    risk_score: Optional[float] = None
    recommended_decision: Optional[str] = None
    detected_risks: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    confidence: Optional[float] = None
    prompt_version: Optional[str] = None
    latency_ms: Optional[int] = None
    usage: Optional[dict] = field(default_factory=dict)
    error_message: Optional[str] = None

    def to_dict(self):
        return asdict(self)

class LLMRiskJudge:
    def __init__(self, config_dir: Path, prompts_dir: Path):
        self.config_dir = config_dir
        self.prompts_dir = prompts_dir
        self.config = self._load_config()
        self.prompt_template = self._load_prompt()
        self.enabled = self.config.get("enabled", False)
        
        provider_config = self.config.get("provider", {})
        self.api_key = os.getenv(provider_config.get("api_key_env", "GROQ_API_KEY"))
        self.model = os.getenv(provider_config.get("model_env", "LLM_JUDGE_MODEL"), provider_config.get("default_model", "llama-3.1-8b-instant"))
        self.timeout = provider_config.get("timeout_seconds", 8)
        self.max_retries = provider_config.get("max_retries", 1)

    def _load_config(self) -> dict:
        config_path = self.config_dir / "llm_judge_policies.yaml"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to load LLM judge config: {e}")
        return {}

    def _load_prompt(self) -> dict:
        prompt_path = self.prompts_dir / "judges" / "banking_tool_risk_judge.v1.yaml"
        if prompt_path.exists():
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to load LLM judge prompt: {e}")
        return {}

    def _render_prompt(self, request: LLMRiskJudgeRequest) -> str:
        # Simple string replacement since we don't assume jinja2 is available in this specific runtime module
        user_prompt = self.prompt_template.get("user_prompt", "")
        user_prompt = user_prompt.replace("{{ task_type }}", str(request.task_type))
        user_prompt = user_prompt.replace("{{ agent_id }}", str(request.agent_id))
        user_prompt = user_prompt.replace("{{ tool_id }}", str(request.tool_id))
        user_prompt = user_prompt.replace("{{ action }}", str(request.action))
        
        payload_summary = str(request.payload_summary)
        max_chars = self.config.get("runtime", {}).get("max_payload_chars", 3000)
        if len(payload_summary) > max_chars:
            payload_summary = payload_summary[:max_chars] + "... [truncated]"
        user_prompt = user_prompt.replace("{{ payload_summary }}", payload_summary)
        
        # Strip out optional template blocks if missing
        if request.candidate_output:
            user_prompt = user_prompt.replace("{% if candidate_output %}", "").replace("{% endif %}", "")
            user_prompt = user_prompt.replace("{{ candidate_output }}", str(request.candidate_output))
        else:
            user_prompt = user_prompt.split("{% if candidate_output %}")[0] + (user_prompt.split("{% endif %}")[1] if "{% endif %}" in user_prompt else "")

        if request.retrieved_context:
            user_prompt = user_prompt.replace("{% if retrieved_context %}", "").replace("{% endif %}", "")
            user_prompt = user_prompt.replace("{{ retrieved_context }}", str(request.retrieved_context))
        else:
            user_prompt = user_prompt.split("{% if retrieved_context %}")[0] + (user_prompt.split("{% endif %}")[1] if "{% endif %}" in user_prompt else "")
            
        if request.policy_context:
            user_prompt = user_prompt.replace("{% if policy_context %}", "").replace("{% endif %}", "")
            user_prompt = user_prompt.replace("{{ policy_context }}", str(request.policy_context))
        else:
            user_prompt = user_prompt.split("{% if policy_context %}")[0] + (user_prompt.split("{% endif %}")[1] if "{% endif %}" in user_prompt else "")
            
        if request.risk_context:
            user_prompt = user_prompt.replace("{% if risk_context %}", "").replace("{% endif %}", "")
            user_prompt = user_prompt.replace("{{ risk_context }}", json.dumps(request.risk_context))
        else:
            user_prompt = user_prompt.split("{% if risk_context %}")[0] + (user_prompt.split("{% endif %}")[1] if "{% endif %}" in user_prompt else "")

        return user_prompt

    def _determine_task_type(self, action: str) -> Optional[str]:
        tasks = self.config.get("tasks", {})
        for task_name, task_config in tasks.items():
            if not task_config.get("enabled", False):
                continue
            if action in task_config.get("actions", []):
                return task_name
        return None

    def evaluate(self, request: LLMRiskJudgeRequest) -> LLMRiskJudgeResponse:
        start_time = time.perf_counter()
        
        # 1. Check if completely disabled
        if not self.enabled:
            return LLMRiskJudgeResponse(judge_status="not_run", error_message="LLM Judge is disabled globally.")

        # 2. Map action to task type if not provided
        if not request.task_type:
            task_type = self._determine_task_type(request.action)
            if not task_type:
                return LLMRiskJudgeResponse(judge_status="not_run", error_message="Action not mapped to any judge task.")
            request.task_type = task_type

        task_config = self.config.get("tasks", {}).get(request.task_type, {})
        if not task_config.get("enabled", False):
            return LLMRiskJudgeResponse(judge_status="not_run", error_message=f"Task type {request.task_type} is disabled.")

        # 3. Check configuration availability
        if not self.api_key or not self.model:
            return LLMRiskJudgeResponse(judge_status="not_configured", error_message="API key or Model is missing.")

        system_prompt = self.prompt_template.get("system_prompt", "")
        user_prompt = self._render_prompt(request)
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 4. Execute LLM Call
        try:
            # Using Groq openai compatible endpoint
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            
            # Parse strict JSON
            result = json.loads(content)
            
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            
            return LLMRiskJudgeResponse(
                judge_status="success",
                model=self.model,
                task_type=request.task_type,
                risk_score=result.get("risk_score"),
                recommended_decision=result.get("recommended_decision"),
                detected_risks=result.get("detected_risks", []),
                reasons=result.get("reasons", []),
                confidence=result.get("confidence"),
                prompt_version=self.prompt_template.get("version", "unknown"),
                latency_ms=latency_ms,
                usage=usage
            )

        except requests.exceptions.Timeout:
            return LLMRiskJudgeResponse(
                judge_status="timeout",
                error_message="LLM API request timed out.",
                latency_ms=int((time.perf_counter() - start_time) * 1000)
            )
        except json.JSONDecodeError:
            return LLMRiskJudgeResponse(
                judge_status="invalid_response",
                error_message="Failed to parse LLM response as JSON.",
                latency_ms=int((time.perf_counter() - start_time) * 1000)
            )
        except Exception as e:
            return LLMRiskJudgeResponse(
                judge_status="error",
                error_message=f"LLM API request failed: {str(e)}",
                latency_ms=int((time.perf_counter() - start_time) * 1000)
            )
