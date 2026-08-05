# Changelog

## 6.2.0-generic-analytics — 2026-08-05

### Added

- Registry-driven `MeasureDefinition`, `AggregationSpec`, `EntityDefinition` and richer Metric/Method/Recipe/Visualization metadata.
- Deterministic field aggregations for value count, cardinality, sum, average, min/max, stats, extended stats and percentiles.
- Typed field-measure Dataset columns, generic additive rollups with non-additive guards, task-aware FeatureSummary and within-group contribution.
- Evidence v2 raw OpenSearch artifacts, source/calculation/statistical tables, used-only technical definitions, exact Claim Trace, owner-scoped artifact download and hash verification.
- Evidence Drawer pagination, complete CSV/JSON download, calculation/definition/claim views and material-only QA presentation.
- Config-only generic field/measure/entity fixtures, semantic equivalence and domain-token guardrails.
- `docs/internal_handoff/00_START_HERE.md` through `11_NEW_SESSION_HANDOFF_PROMPT.md`, including a copy-ready prompt for a fresh internal AI session.

### Changed

- Agent A/B/C safe payloads now include governed Measure/Entity/Method/task/grain/completeness information without physical paths or tool surfaces.
- Formal Metric filtered-count formulas bind a versioned ValueDictionary instead of relying on representative status tokens.
- MCP smoke accepts arbitrary repeated `--dimension-field` parameters.
- ERROR/FATAL QA blocks formal Agent C/Grounding conclusions; user Evidence no longer renders per-rule QA pass/fail.

### Security

- Model-invisible fields and their measures are excluded from retrieval.
- Raw artifacts omit detail hits, enforce server-generated paths/size/hash validation, and are resolved through Answer ownership.
- CSV artifact hashes cover exact downloadable bytes and CSV formula injection remains neutralized.
