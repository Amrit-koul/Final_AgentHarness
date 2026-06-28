"""
Compliance Agent
Ensures all actions meet regulatory and policy requirements
"""
from typing import Dict, Any, Optional, List
from banking_agents.collections_domain.agents.base import BaseAgent, AgentDecision


class ComplianceAgent(BaseAgent):
    """
    Validates all collection actions for compliance
    """
    
    def __init__(self):
        super().__init__(
            agent_id="compliance",
            name="Compliance Agent",
        )
    
    async def reason(
        self,
        account_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Validate compliance for planned action
        """
        # Get planned action from context
        nba_data = context.get("next_best_action_decision", {}).get("data", {}) if context else {}
        action = nba_data.get("action", "unknown")
        channel = nba_data.get("WHEN", {}).get("channel", "whatsapp")
        timing = nba_data.get("WHEN", {}).get("timing", "10:00 IST")
        
        # Get message if available
        message = context.get("generated_message", "")
        
        contacts_today = len([h for h in account_data.get("call_history", []) if "today" in str(h).lower()])
        system_prompt, prompt = self._render_prompt(
            "collections_compliance",
            action=action,
            channel=channel,
            timing=timing,
            dpd=account_data.get("dpd", 0),
            outstanding=f"{account_data.get('outstanding', 0):,}",
            message=message if message else "N/A - non-communication action",
            persona=account_data.get("persona", "Unknown"),
            status=account_data.get("status", "Unknown"),
            contacts_today=contacts_today,
            nba_context=nba_data,
        )
        try:
            result = await self._llm_json_reason(prompt, system_prompt, temperature=0.1)
            
            confidence = float(result.get("confidence", 0.95))
            reasoning = result.get("reasoning", [])
            
            compliance_status = result.get("compliance_status", "passed")
            
            data = {
                "compliance_status": compliance_status,
                "checks_performed": result.get("checks_performed", []),
                "violations": result.get("violations", []),
                "warnings": result.get("warnings", []),
                "required_modifications": result.get("required_modifications", []),
                "approval_needed": result.get("approval_needed", False),
                "approval_level": result.get("approval_level"),
                "compliance_score": result.get("compliance_score", 100),
                "raw_llm_output": result,
            }
            
            # Escalate if not passed
            escalate = compliance_status != "passed"
            escalation_reason = None
            if escalate:
                if compliance_status == "blocked":
                    escalation_reason = f"BLOCKED: {', '.join(data['violations'])}"
                else:
                    escalation_reason = f"Review needed: {data.get('approval_level', 'supervisor')}"
            
            return AgentDecision(
                action="compliance_validated",
                confidence=confidence,
                reasoning=reasoning,
                data=data,
                escalate=escalate,
                escalation_reason=escalation_reason,
            )
        
        except Exception as e:
            return await self._fallback_compliance(action, channel, timing, message, str(e))
    
    async def _fallback_compliance(
        self,
        action: str,
        channel: str,
        timing: str,
        message: str,
        error: str,
    ) -> AgentDecision:
        """Fallback compliance checking"""
        # Simple rule-based checks
        violations = []
        warnings = []
        
        # Check timing
        try:
            hour = int(timing.split(":")[0])
            if hour < 7 or hour >= 19:
                violations.append("Contact time outside RBI allowed hours (7 AM - 7 PM)")
        except:
            warnings.append("Could not parse timing")
        
        # Check message for coercive language
        if message:
            coercive_words = ["court", "police", "jail", "arrest", "lawsuit", "legal action"]
            if any(word in message.lower() for word in coercive_words):
                warnings.append("Message contains potentially coercive language")
        
        # Check action type
        if action == "escalate_to_legal":
            warnings.append("Legal action requires compliance officer review")
        
        compliance_status = "blocked" if violations else "review_needed" if warnings else "passed"
        
        data = {
            "compliance_status": compliance_status,
            "violations": violations,
            "warnings": warnings,
            "checks_performed": [
                {"check": "rbi_timing", "status": "pass" if not violations else "fail"},
                {"check": "message_content", "status": "warning" if warnings else "pass"},
            ],
            "fallback": True,
        }
        
        return AgentDecision(
            action="compliance_validated",
            confidence=0.7,
            reasoning=[
                "Fallback rule-based compliance check",
                f"⚠️ LLM compliance failed: {error}",
                f"Status: {compliance_status}",
            ],
            data=data,
            escalate=compliance_status != "passed",
            escalation_reason="Compliance check in fallback mode" if compliance_status != "passed" else None,
        )


