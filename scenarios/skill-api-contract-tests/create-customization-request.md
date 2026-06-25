/create-skill

Create a workspace skill named "api-contract-test-design".

It is for business analysts, testers, and ordinary developers who paste a REST API specification and ask for comprehensive test cases.

At runtime, the user should only invoke `/api-contract-test-design` and paste the contract.

Create a Skill with:

- `SKILL.md`
- reference notes for boundary analysis, API risk checklist and contract gap checklist
- a test matrix template

The skill must:

1. extract every explicit contract rule and assign a requirement ID;
2. distinguish explicit behavior from missing contract decisions;
3. use equivalence partitioning and boundary-value analysis;
4. test missing, null, empty, whitespace, wrong type, invalid format, unsupported enum and excessive length where relevant;
5. test cross-field constraints;
6. separate authentication from authorization;
7. test idempotency, retry, timeout and concurrent submission;
8. test time, timezone and exact boundary behavior;
9. verify status codes and response schemas;
10. identify security and privacy test cases without inventing rules;
11. mark tests blocked by missing contract decisions;
12. link every test case to requirements and risk categories;
13. prioritize P0, P1 and P2;
14. identify automation candidates;
15. deduplicate semantically equivalent tests;
16. output Chinese Markdown tables.

Set:

```yaml
user-invocable: true
disable-model-invocation: true
```

Do not pin a model.

Save it as a Workspace skill.
