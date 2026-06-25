# Output Template

Use Chinese Markdown tables.

## Contract Summary

Summarize endpoint, method, required headers, request body, response body and primary business rules in 3-6 bullets.

## Requirement List

| Requirement ID | Source | Rule | Notes |
|---|---|---|---|

Assign IDs such as `REQ-001`, `REQ-002`.

## Contract Gaps

| Gap ID | Missing decision | Why it matters | Blocked tests |
|---|---|---|---|

Assign IDs such as `GAP-001`, `GAP-002`.

## Test Matrix

| Test Case ID | Priority | Requirement IDs | Risk Category | Preconditions | Input | Steps | Expected Result | Test Type | Automation Candidate | Notes |
|---|---|---|---|---|---|---|---|---|---|---|

Use IDs such as `TC-001`, `TC-002`.

Priority:

- P0: critical correctness, money movement, security, idempotency or data integrity
- P1: important validation, boundaries or common negative paths
- P2: lower-risk compatibility, formatting or edge cases

## Requirement Traceability

| Requirement ID | Covered by Test Case IDs | Coverage Notes |
|---|---|---|

## Automation Candidates

| Test Case ID | Candidate Type | Automation Notes |
|---|---|---|

Candidate types: API integration, contract test, negative validation, concurrency, manual review.

## Deduplication Notes

List semantically equivalent cases that were merged.
