---
name: api-contract-test-design-skill-creator
description: Design comprehensive API contract test cases from pasted REST API contracts. Use for requests involving boundary values, authorization, idempotency, response schema checks, traceability, contract gaps, or automation candidates.
---

# API Contract Test Design

Design API contract test cases from the contract supplied by the user. Keep the output in Chinese unless the user asks otherwise.

## Workflow

1. Extract only explicit contract facts and assign stable Requirement IDs.
2. Separate missing decisions into Contract Gaps before writing test cases.
3. Identify request headers, request body fields, response fields, status codes, cross-field rules and stateful behavior.
4. Apply equivalence partitioning and boundary-value analysis.
5. Cover authentication, authorization, idempotency, retries, client timeouts and concurrent submissions when the contract implies them.
6. Build a deduplicated test matrix with Requirement IDs, priority and automation suitability.
7. Mark any test blocked by a named Contract Gap instead of inventing expected behavior.

## Reference Loading

- Read `references/boundary-and-partitions.md` when fields include numeric limits, text length, enums, timestamps, optional fields or cross-field rules.
- Read `references/risk-gap-checklist.md` when identifying negative tests, security/privacy cases, idempotency risks or missing contract decisions.
- Read `references/output-template.md` before producing the final Chinese Markdown tables.

## Output Contract

Return these sections:

1. Contract summary
2. Requirement list
3. Contract gaps
4. Test matrix
5. Requirement traceability
6. Automation candidates
7. Deduplication notes

Do not write executable test code unless the user explicitly asks for code.
