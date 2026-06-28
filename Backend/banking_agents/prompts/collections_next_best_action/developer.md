# Task

Determine the next best action for this account.

## Account profile

- Account ID: $account_id
- Persona: $persona
- Persona confidence: $persona_confidence
- DPD: $dpd
- Outstanding: ₹$outstanding
- EMI: ₹$emi
- CIBIL: $cibil

## Scores

- Ability to Pay: $ability_to_pay/100
- Intent to Pay: $intent_to_pay/100
- Self-cure Probability: $self_cure/100

## Behavioral insights

- Recommended Channel: $channel
- Best Contact Time: $contact_time
- Recommended Tone: $tone
- Predicted Response Rate: $predicted_response_rate

## Previous status

- Current Status: $status
- Last Action: $last_action

## Context from prior agents

Persona Reasoning:
$persona_reasoning

Behavioral Strategy:
$behavioral_strategy

Use the WHO-WHAT-WHEN framework and return only valid JSON.
