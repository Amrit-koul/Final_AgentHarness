# Few-shot examples

## Example 1

Input: “What is the bank policy for nominee update?”

Output route: `policy_navigator`

Audit summary: “Route to policy navigator for account servicing policy retrieval.”

## Example 2

Input: “Customer has DPD 62 and broken PTP twice. Should we trigger field visit?”

Output route: `collections_advisor`

Human approval: `true`

Audit summary: “Route to collections advisor; field visit recommendation requires policy and conduct checks.”

## Example 3

Input: “Disable collections_workflow_agent for testing.”

Output route: `control_plane`

Human approval: `true`

Audit summary: “Administrative control-plane action requested; requires authorized operator approval.”
