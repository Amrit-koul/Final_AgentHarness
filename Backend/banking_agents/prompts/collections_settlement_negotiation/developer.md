# Task

Determine settlement negotiation strategy.

## Account

- Persona: $persona
- DPD: $dpd
- Outstanding: ₹$outstanding
- EMI: ₹$emi
- Product: $product

## Scores

- Ability to Pay: $ability_to_pay/100
- Intent to Pay: $intent_to_pay/100
- Self-cure Probability: $self_cure/100

## Context

- Current Status: $status
- Previous Action: $previous_action

## OTS eligibility check

- DPD at least 30: $dpd_eligible
- Outstanding above ₹1L: $outstanding_eligible

Return only valid JSON.
