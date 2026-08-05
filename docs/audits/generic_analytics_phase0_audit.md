# Generic Analytics Upgrade — Phase 0 Architecture and Gap Audit

- Date: 2026-08-05
- Upgrade branch: `MI-GENERIC-ANALYTICS`
- Remote baseline: `origin/MI-NEW`
- Baseline commit: `dbe31fdc198cbc07975bfcbe20163f647b01aacc`
- User upgrade plan SHA-256: `03ec0531aa428deb800bda3179637d5dd3365379cf0d548db0ccd89b2e6fa990`
- Result: **PASSED — implementation may proceed**

## 1. Baseline and worktree audit

`git fetch origin MI-NEW` confirmed that local `MI-NEW`, `origin/MI-NEW`, and the reviewed baseline commit all resolve to `dbe31fdc198cbc07975bfcbe20163f647b01aacc`. There are no later remote commits to absorb or audit. The clone was clean before branch creation, and no unrelated user changes were present.

The frozen V6.1 master specification hash initially differed when hashing the Windows checkout bytes. Recomputing its SHA-256 after the repository-required UTF-8/LF normalization produced `3762adc6ca42745151d01894c835f6d80c9dfb84a6e1ce9624e8b026ed85b6c6`, exactly matching `AGENTS.md`. This was a CRLF checkout effect, not a content drift or architecture conflict.

## 2. Authority review and conflict register

The following sources were read in authority order before implementation:

1. `AGENTS.md`.
2. `docs/baseline/OpenSearch_ChatBI_V6.1_Master_Execution_Spec_含_opensearch-agent_架构校准.md` in full.
3. The current upgrade request, including its replacement Evidence rules.
4. `OpenSearch_ChatBI_通用智能分析能力升级执行方案_v1.md` in full.
5. Current README, `project_memory.md`, integration documents, audits, test report, delivery manifest, and approved behavior encoded in source/tests.

| Topic | Apparent tension | Resolution |
|---|---|---|
| Evidence QA display | V6.1 material preserved detailed QA structures; the upgrade explicitly removes per-rule pass/fail from user Evidence | Keep the complete QA/audit artifact and FATAL/ERROR gates internally; expose only overall status, material limitations, blocked reasons, and reconciliation summary |
| Source evidence | V6.1 retained query/result provenance but not the full immutable aggregation artifact contract | The upgrade request is more specific and therefore adds raw aggregation artifacts, normalized source tables, calculation tables, technical definitions, and cell/value-path claim traces without exposing unrestricted `_source` |
| Business examples | Existing fixtures/prompts contain Channel/Use Case/Template/Source System examples | Keep examples only in Mock/Golden fixtures; formal Semantic, Query, Analytics, and Presentation modules must remain capability/registry driven |
| Frozen agent layout | The upgrade asks for richer decisions and tools | Preserve one StateGraph and Agents A/B/C, with C1→Host→C2; add no supervisor and no free tool loop |

No unresolved conflict changes a frozen architecture boundary.

## 3. Reusable architecture

The existing V6.1 implementation provides sound extension points:

- one modular FastAPI composition root and one LangGraph StateGraph;
- strict Pydantic contracts and generated OpenAPI/TypeScript snapshots;
- Semantic compiler/package/retriever/resolver and policy-aware field descriptors;
- logical QueryPlan finalization, N-dimensional terms/composite routing, cardinality/bucket budgets, deterministic AST/compiler/validator ownership, and dependent query plumbing;
- allowlisted Gateway/MCP adapters, retry/timeout, composite paging, response-size checks, and Mock fixtures;
- result parsing, stable row identity, DatasetBundle, Metric Engine, Rollup, statistics, QA/reconciliation, C1/Host/C2, grounding, dashboard, and Evidence building;
- owner/subject-scoped sessions and answers, checkpoints, idempotency, locks, cancellation, audit logging, and frontend safe-chart rendering.

These modules will be upgraded incrementally rather than replaced.

## 4. Confirmed gaps

### Semantic and contracts

- `CanonicalField.capabilities` is generic but numeric fields expose only coarse `metric`; explicit aggregation capabilities are missing.
- No governed `MeasureDefinition`/`AggregationSpec` registry exists for field-level `value_count`, `cardinality`, `sum`, `avg`, `min`, `max`, `stats`, `extended_stats`, or `percentiles`.
- Metric and Method contracts lack several user-facing technical-definition fields and explicit additive/non-additive semantics.
- No generic `EntityDefinition`/member-resolution contract exists.
- Semantic Package/Retriever/Resolver do not compile, index, or bind measure/entity candidates.

### Query, DSL, and execution

- `QueryStep.measures` currently contains only metric IDs.
- `DslCompiler._build_ast` converts every requested measure to `document_count`; the compiler emits dimension buckets but no field metric aggregations.
- Dataset contracts are therefore forced to `record_count`, with other raw metric values left untyped in metadata.
- Composite paging is executed and checked, but the full raw page/bucket material is not retained as an immutable, downloadable artifact tied to `CompiledQuery` and `ExecutionRecord`.

### Analytics and Agents C1/C2

- Feature summaries are dataset-wide rather than task-aware.
- Statistical tool requests/results do not consistently expose partition/category/time inputs, calculation-table IDs, stable value paths, or technical method metadata.
- Rollup needs explicit additive/non-additive guards and general within-group contribution output.
- Agent C receives governed data, but the payload and grounder require richer source/calculation/statistical bindings.

### Evidence, API, and frontend

- Current Evidence stores query summaries and hashes but not a complete source-result artifact/table lineage.
- Metric-derived, rollup, comparison, statistical, and chart-input calculation tables are not first-class immutable evidence objects.
- Technical definitions are shallow and do not include all required formula/aggregation/null/time/approximation details.
- Claim references cannot yet address calculation-table cells or arbitrary statistical result value paths.
- User Evidence currently includes every `DataQARecord`; this violates the replacement display rule.
- Evidence APIs/UI need paged preview and owner-checked JSON/CSV download endpoints.

### Handoff and verification

- Existing integration documentation is V6.1-oriented and does not provide the requested `docs/internal_handoff/00`–`09` operational path for config-only onboarding and the new Evidence lineage.
- Generic field/measure/entity onboarding, semantic equivalence, domain-token, arbitrary dimension/cardinality, non-additive, and Evidence-specialized tests need to be added.

## 5. Contract, persistence, and UI impact

- Contracts will gain versioned aggregation/measure/entity definitions, richer resolved/query semantics, typed measure columns, source/calculation/statistical artifact metadata, technical definitions, and generalized claim targets.
- Existing fields remain backward-compatible where practical so persisted V6.1 snapshots and fixtures can be migrated deterministically.
- A database migration is expected for immutable Evidence artifact metadata and ownership; large content will use the configured artifact directory with content-addressed names and strict owner/session/answer lookup.
- Raw credentials, endpoints, unrestricted physical details, unrestricted `_source`, prompts, and secrets remain excluded from model/frontend Evidence.
- Frontend generated types, Evidence model, drawer tabs, paged tables, download state, limitation state, and component tests must change together.

## 6. Phased implementation plan

1. Contracts and config-only Semantic registries for measures, entities, method/recipe/visualization technical metadata.
2. Resolver and Agent A/B safe candidate/payload upgrades.
3. General AggregationSpec AST/compiler/validator and typed ResultNormalizer support.
4. Immutable raw/source artifacts, composite lineage, size limits, and owner-scoped storage/API.
5. Metric/Rollup/statistics/task-aware FeatureSummary, C1 tool requests, C2 material, and generalized grounding.
6. Evidence Package/Builder and frontend Evidence Drawer redesign.
7. Mock/Golden/config-only/security/architecture/integration test expansion and complete regression.
8. Internal handoff, migrations, generated schemas/types, release/test/gate reports, phased commits, and push.

Each phase must preserve deterministic ownership, formal/Mock isolation, and required-task coverage. Gate failure will be fixed before advancing.

## 7. Phase 0 risks and decisions

- The change surface is intentionally broad; compatibility defaults and schema snapshot review will keep migrations explicit.
- Large Evidence content must not inflate logs/checkpoints; artifact metadata and bounded previews will be persisted separately from content-addressed files.
- Exact terms aggregation completeness is distinguishable from top-N partial results; composite remains the complete high-cardinality path within configured page/bucket limits.
- External real LLM/MCP/data verification is unavailable. Adapter contracts, recorded fixtures, cutover checks, and Shadow/UAT commands remain mandatory; no real-path result will be claimed locally.

