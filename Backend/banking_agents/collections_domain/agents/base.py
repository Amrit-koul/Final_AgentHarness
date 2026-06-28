"""
Base Agent Framework
Provides memory, reasoning loops, confidence scoring, and escalation logic
"""
from __future__ import annotations
import os
import json
import uuid
from abc import ABC, abstractmethod
from string import Template
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import httpx

from banking_agents.prompts import prompt_registry


class AgentConfidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AgentDecision:
    """Represents an agent's decision with confidence and reasoning"""
    def __init__(
        self,
        action: str,
        confidence: float,
        reasoning: List[str],
        data: Dict[str, Any],
        escalate: bool = False,
        escalation_reason: Optional[str] = None,
        next_agent: Optional[str] = None,
    ):
        self.action = action
        self.confidence = confidence
        self.reasoning = reasoning
        self.data = data
        self.escalate = escalate
        self.escalation_reason = escalation_reason
        self.next_agent = next_agent
        self.timestamp = datetime.now().isoformat()
        self.decision_id = uuid.uuid4().hex[:12]


class AgentMemory:
    """Agent memory for storing decisions, learnings, and context"""
    def __init__(self):
        self.decisions: List[AgentDecision] = []
        self.learnings: Dict[str, Any] = {}
        self.context: Dict[str, Any] = {}
    
    def add_decision(self, decision: AgentDecision):
        self.decisions.append(decision)
        # Keep only last 50 decisions
        if len(self.decisions) > 50:
            self.decisions = self.decisions[-50:]
    
    def add_learning(self, key: str, value: Any):
        """Store learned patterns for future decisions"""
        self.learnings[key] = value
    
    def get_learning(self, key: str, default: Any = None) -> Any:
        return self.learnings.get(key, default)
    
    def update_context(self, context: Dict[str, Any]):
        self.context.update(context)
    
    def get_recent_decisions(self, count: int = 5) -> List[AgentDecision]:
        return self.decisions[-count:]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decisions": [
                {
                    "action": d.action,
                    "confidence": d.confidence,
                    "reasoning": d.reasoning,
                    "timestamp": d.timestamp,
                    "decision_id": d.decision_id,
                }
                for d in self.decisions[-10:]
            ],
            "learnings": self.learnings,
            "context": self.context,
        }


class BaseAgent(ABC):
    """Base class for all ARIA agents"""
    
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self.memory = AgentMemory()
        self.llm_client = self._init_llm_client()
        self.model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    
    def _init_llm_client(self) -> Optional[httpx.AsyncClient]:
        """Initialize LLM client for reasoning (Groq — OpenAI-compatible)"""
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            return None
        return httpx.AsyncClient(
            verify=False,
            base_url="https://api.groq.com/openai/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )
    
    # Global cache for LLM reasoning to reduce redundant API calls
    _llm_cache: Dict[str, str] = {}

    async def _llm_reason(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 800,
    ) -> str:
        """Call LLM for reasoning with simple caching"""
        cache_key = f"{self.model}:{temperature}:{system_prompt}:{prompt}"
        if cache_key in self._llm_cache:
            return self._llm_cache[cache_key]
            
        if not self.llm_client:
            raise RuntimeError(f"GROQ_API_KEY not configured for {self.name}")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.llm_client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            
            # Save to cache (limit size to prevent memory leak)
            if len(self._llm_cache) > 1000:
                self._llm_cache.clear()
            self._llm_cache[cache_key] = content
            
            return content
        except Exception as e:
            raise RuntimeError(f"LLM reasoning failed in {self.name}: {str(e)}")
    
    async def _llm_json_reason(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """Call LLM and parse JSON response"""
        response = await self._llm_reason(prompt, system_prompt, temperature)
        
        # Extract JSON from response (handle markdown code blocks)
        text = response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from text
            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            raise ValueError(f"Failed to parse JSON from LLM response: {text[:200]}")

    def _render_prompt(self, prompt_id: str, **variables: Any) -> Tuple[str, str]:
        """Load a Markdown prompt and render its developer template.

        The main system instructions live in system.md. The dynamic task prompt
        lives in developer.md and uses string.Template placeholders such as
        $account_id. few_shots.md is appended to the user prompt so examples stay
        out of Python code while still being available to the model.
        """
        loaded = prompt_registry.load(prompt_id)
        safe_vars = {key: self._prompt_value(value) for key, value in variables.items()}
        user_prompt = Template(loaded.developer).safe_substitute(safe_vars)
        if loaded.few_shots.strip():
            user_prompt = f"{user_prompt.strip()}\n\n# Examples and response contract\n{loaded.few_shots.strip()}"
        return loaded.system, user_prompt

    @staticmethod
    def _prompt_value(value: Any) -> str:
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False, indent=2, default=str)
        except TypeError:
            return str(value)
    
    def _calculate_confidence(
        self,
        factors: Dict[str, float],
        weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[float, AgentConfidence]:
        """
        Calculate confidence score from multiple factors
        
        Args:
            factors: Dict of factor_name -> score (0-1)
            weights: Optional weights for each factor (must sum to 1.0)
        
        Returns:
            Tuple of (confidence_score, confidence_level)
        """
        if not factors:
            return 0.5, AgentConfidence.MEDIUM
        
        if weights is None:
            # Equal weights
            weights = {k: 1.0 / len(factors) for k in factors}
        
        confidence = sum(factors[k] * weights.get(k, 0) for k in factors)
        confidence = max(0.0, min(1.0, confidence))
        
        if confidence >= 0.8:
            level = AgentConfidence.HIGH
        elif confidence >= 0.5:
            level = AgentConfidence.MEDIUM
        else:
            level = AgentConfidence.LOW
        
        return confidence, level
    
    def should_escalate(
        self,
        confidence: float,
        account_data: Dict[str, Any],
        threshold: float = 0.5,
    ) -> Tuple[bool, Optional[str]]:
        """Determine if decision should be escalated"""
        # Low confidence
        if confidence < threshold:
            return True, f"Confidence {confidence:.2f} below threshold {threshold}"
        
        # High-value accounts always need review
        outstanding = account_data.get("outstanding", 0)
        if outstanding > 5000000:
            return True, f"High-value account: ₹{outstanding:,}"
        
        # Legal/hostile cases need human oversight
        persona = account_data.get("persona", "")
        if "hostile" in persona or account_data.get("dpd", 0) > 90:
            return True, f"Sensitive case: {persona}, DPD {account_data.get('dpd')}"
        
        return False, None
    
    @abstractmethod
    async def reason(
        self,
        account_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Core reasoning method - must be implemented by each agent
        
        Args:
            account_data: Account information
            context: Optional additional context
        
        Returns:
            AgentDecision with action, confidence, and reasoning
        """
        pass
    
    async def execute(
        self,
        account_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Execute agent reasoning and store decision in memory
        """
        # Update context in memory
        if context:
            self.memory.update_context(context)
        
        # Execute reasoning
        decision = await self.reason(account_data, context)
        
        # Store decision in memory
        self.memory.add_decision(decision)
        
        # Check if should escalate
        if not decision.escalate:
            should_esc, reason = self.should_escalate(
                decision.confidence,
                account_data,
            )
            if should_esc:
                decision.escalate = True
                decision.escalation_reason = reason
        
        return decision
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """Get summary of agent memory for debugging/monitoring"""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.name,
            "memory": self.memory.to_dict(),
        }

