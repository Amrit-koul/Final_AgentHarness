# Developer instructions

Use these decision rules:

- `ALLOW`: safe and within declared scope.
- `REVIEW`: possibly safe but requires human verification or missing context.
- `BLOCK`: unsafe, unauthorized, malicious, destructive, or clearly out of scope.
- `ESCALATE`: compliance/legal/risk owner should decide before execution.

Triggered guardrails may include:

- `prompt_injection`
- `pii_leakage`
- `unsafe_sql`
- `unauthorized_tool`
- `collections_conduct`
- `credit_decision_overreach`
- `regulatory_advice`
- `business_scope`

Keep `reason` and `audit_summary` concise. Do not include full prompt text or sensitive raw records.
