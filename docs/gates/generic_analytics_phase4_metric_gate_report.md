# Generic Analytics Phase 4 Metric Binding Gate

Date: 2026-08-05

## Scope

Remove the last representative-token assumption from governed filtered-count Metric binding.

## Result

- `MetricDefinition` now declares optional versioned `value_dictionary_ids` alongside explicit `source_field_ids`.
- Semantic compilation requires a filtered-count formula to resolve exactly one compatible dictionary and validates only its source field/groups.
- Resolver derives required fields from the configured dictionary or an unambiguous backward-compatible match; it no longer searches for `success/failure` tokens.
- Analytics execution selects the dictionary referenced by the active Metric definitions and blocks ambiguous/missing bindings.
- Evidence technical definitions expose the dictionary and source-field IDs used by the metric.
- The synthetic failure-rate fixture was migrated to `status_group.v1` plus `sub_message.status`; package compilation produced `sp_02fd263e8f9d5a91`.

Verification: Ruff and mypy passed; semantic/query/pipeline/metric/API focused regression passed 30/30 in 17.70 s. A subsequent full suite exposed one test-cleanup assumption because Evidence now creates nested artifact files; the owner-scoped orchestration test cleanup was corrected and the failing test passed in 2.17 s. Final full verification is recorded in the release gate.

Gate: PASS.
