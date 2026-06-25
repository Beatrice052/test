/skill-creator

Create a skill named "api-contract-test-design-skill-creator".

This skill is for testers, business analysts and ordinary developers who paste a REST API contract and ask for comprehensive API contract test cases.

Runtime use:

- The user invokes `/api-contract-test-design-skill-creator`.
- The user pastes the API contract or rough API document.
- The user should not need to paste a testing checklist, boundary-analysis method, output template or prompt-engineering instructions.

Skill design requirements:

1. Keep `SKILL.md` concise and focused on the workflow.
2. Put detailed boundary analysis, API risk checks, contract gap checks and output table format into `references/`.
3. Do not create README, installation guides, changelogs or unrelated documentation.
4. Do not include scripts unless they are truly needed; this scenario should be reference-driven.
5. Use only contract facts supplied by the user.
6. Separate explicit requirements from missing contract decisions.
7. Mark tests blocked by missing decisions instead of inventing behavior.
8. Generate Chinese Markdown output.
9. Include requirement IDs, contract gaps, test case IDs, priority, risk category, preconditions, input, steps, expected result, test type, automation candidate and traceability.
10. Cover boundary values, equivalence partitions, missing/null/empty/wrong-type values, enum cases, cross-field constraints, authentication, authorization, idempotency, retry, timeout, concurrency, response schema, security and privacy risks.

Reference files to create:

- `references/boundary-and-partitions.md`
- `references/risk-gap-checklist.md`
- `references/output-template.md`

Do not pin a model and do not connect to external judge services.
