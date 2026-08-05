# Generic Analytics Upgrade — Phase 1 Gate Report

- Date: 2026-08-05
- Result: **PASSED**
- Scope: generic semantic contracts, config-only registries, safe A/B inputs, governed field aggregation DSL, and typed normalization

## Implemented

- Added closed `AggregationKind`, `AggregationParameters`, `AggregationSpec`, additive-semantics metadata, `MeasureDefinition`, and `EntityDefinition` contracts.
- Extended AnalysisPlan/ResolvedAnalysis/QueryPlan with optional measure/entity decisions while preserving existing V6.1 fixtures.
- Added Measure and Entity YAML registries, package serialization, FTS retrieval candidates, deterministic binding, and dictionary member resolution.
- Expanded mapping-derived capabilities to explicit `aggregate_*` capabilities.
- Made Agent A receive safe Measure/Entity candidates and Agent B receive only resolved semantic aggregation specifications; neither receives physical paths.
- Implemented deterministic OpenSearch DSL for `value_count`, `cardinality`, `sum`, `avg`, `min`, `max`, `stats`, `extended_stats`, and `percentiles`.
- Added finalizer checks that prevent Agent B from changing source field, aggregation, parameters, unit, or additive semantics.
- Added typed single- and multi-value Dataset columns and normalization paths; preserved legacy raw metric metadata for snapshot compatibility.
- Added a synthetic, previously unknown `quality_score` field, generic Measure, and entity dictionary entirely through Mock configuration.
- Regenerated the compiled Mock package, 44 schema snapshots, OpenAPI, and 65 frontend TypeScript schemas.

## Tests actually run

```powershell
pytest -q tests/integration/semantic/test_compile_package.py tests/integration/query/test_plan_compile.py tests/unit/analytics/test_normalizer.py
pytest -q tests/unit/query/test_generic_measure_compiler.py tests/integration/semantic/test_compile_package.py
pytest -q
ruff check .
ruff format --check .
mypy app
python ../scripts/check_schema_snapshots.py
```

| Check | Result |
|---|---:|
| Existing semantic/query/normalizer regression | 22 passed |
| New aggregation/config-only targeted suite | 17 passed |
| Full backend regression after fixes | 311 passed / 0 failed / 0 skipped; 1 Starlette deprecation warning; 35.86 s |
| Ruff | passed |
| mypy strict | passed; 135 source files |
| Semantic compile | passed; package `sp_408942842315e6fc`, 13 fields |

An intermediate full run found three expected migration issues: inactive internal template examples were being validated and one source-count assertion still expected 11 rows. The compiler now ignores disabled definitions, templates are disabled until filled, the assertion is 12, and the complete rerun passed.

## Gate decision

The formal compiler has no field-name-specific aggregation branch. A new numeric field and Measure enter retrieval→resolution→logical plan→DSL→typed Dataset through configuration. Physical paths remain compiler-owned. **Phase 1 Gate: PASSED.**
