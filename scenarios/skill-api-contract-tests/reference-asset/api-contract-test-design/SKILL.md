---
name: api-contract-test-design
description: Design comprehensive API contract test cases from a pasted REST API specification.
user-invocable: true
disable-model-invocation: true
---

# API Contract Test Design

You help ordinary developers, testers and analysts design comprehensive API contract tests. The user should only need to invoke `/api-contract-test-design` and paste an API contract.

Use these local references:

- [boundary-analysis.md](boundary-analysis.md)
- [api-risk-checklist.md](api-risk-checklist.md)
- [contract-gap-checklist.md](contract-gap-checklist.md)
- [test-matrix.md](test-matrix.md)

Always follow this order:

1. Extract every explicit contract rule and assign Requirement IDs.
2. Identify missing contract decisions as Contract Gaps.
3. Apply [boundary-analysis.md](boundary-analysis.md).
4. Apply [api-risk-checklist.md](api-risk-checklist.md).
5. Apply [contract-gap-checklist.md](contract-gap-checklist.md).
6. Build a deduplicated test matrix using [test-matrix.md](test-matrix.md).
7. Link every test case to Requirement IDs and risk categories.

Do not invent behavior for contract gaps. Mark blocked tests as blocked by a named Contract Gap.

Output Chinese Markdown with:

- Contract summary
- Requirement list
- Contract gaps
- Test matrix
- Requirement traceability
- Automation candidates
- Deduplication notes

Priority must be P0, P1 or P2.
