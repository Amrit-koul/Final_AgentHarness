"""Compatibility shim; bank guardrails live in banking_agents.guardrails.business."""
from banking_agents.guardrails.business import BankingBusinessGuardrails, GuardrailResult
BusinessGuardrails = BankingBusinessGuardrails
