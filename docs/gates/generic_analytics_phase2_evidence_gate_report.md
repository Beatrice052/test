# Generic Analytics Phase 2 Gate Report

Date: 2026-08-05  
Branch: `MI-GENERIC-ANALYTICS`  
Baseline: `dbe31fdc198cbc07975bfcbe20163f647b01aacc`

## Scope

This gate covers post-query analytics and Evidence v2: task-aware typed feature summaries, registered statistical methods (including within-group contribution), ERROR/FATAL QA exclusion, full merged OpenSearch aggregation artifacts, normalized source tables, deterministic calculation tables, technical definitions, exact claim references, owner-scoped artifact reads, and the generic MCP smoke command.

## Architecture decisions

- Raw Evidence content is stored below `APP_ARTIFACT_DIR/evidence` under server-generated IDs. The immutable `AnswerSnapshot` stores the hash, size, owner-mediated download URL, and lineage; API reads first resolve the reference through the requesting subject's answer. This avoids a database schema migration while preserving owner isolation and session recovery.
- Raw aggregation artifacts retain all aggregation buckets returned by the governed query and composite-page lineage, but omit detail hits. The source-result CSV hashes the exact downloadable bytes.
- Complete `DataQARecord` objects remain in the owner-scoped `AnswerSnapshot` and debug/audit path. User Evidence contains only overall status, material warnings, blocked reasons, completeness, and reconciliation summaries.
- Agent C receives bounded validated rows, task/grain/completeness metadata, registered method definitions, and material QA state. It never receives executable code, physical field paths, MCP tool names, or raw DSL.
- MCP smoke coverage now accepts one to three arbitrary `--dimension-field` arguments; representative business fields are no longer part of the command contract.

## Gate evidence

- Semantic compile: PASS, package `sp_77f7f711f130cb97`, 13 fields.
- Ruff check: PASS; Ruff format check: PASS.
- Mypy: PASS, 136 source files.
- Focused backend regression: 77 passed, 1 dependency deprecation warning, 22.72 s.
- Full backend regression: exit 0; 318 tests collected; 41.92 s.
- Frontend TypeScript typecheck: PASS.
- Frontend ESLint: PASS.
- Frontend Vitest: 7 files / 20 tests passed, 2.51 s.
- Frontend production build: PASS, 672 modules, 3.03 s; Vite reported the existing large-chunk advisory.

## Acceptance checks

- Source raw artifact, `CompiledQuery`, execution summary, source table, hash, and answer ownership are mutually traceable.
- Composite page after-keys and merged completeness are retained.
- Source CSV hash is computed over the exact download payload and row count reconciles to aggregation buckets in the API integration fixture.
- Derived Metric/Rollup and statistical outputs expose calculation/table IDs, source IDs, task IDs, grain, inputs, outputs, parameters, row/value paths, completeness, and hashes.
- Claim Trace resolves dataset and statistic references to exact table/artifact IDs and cell/value paths.
- Only definitions used by the current query or host statistical execution are emitted.
- Per-rule QA pass entries are absent from user Evidence; material warnings remain and blocking QA still prevents formal claims.
- Model-invisible fields and their measures are absent from retrieval candidates.
- Physically different but semantically equivalent mappings compile to equivalent query semantics and normalized results.
- Formal decision modules pass the domain-specific implementation-name guardrail.

## Result

PASS. The phase may proceed to final schema synchronization, end-to-end verification, and internal handoff documentation.
