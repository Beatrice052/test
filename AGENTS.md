# Instructions for AI agents continuing this project

This repository is an external-network Mock-first implementation that must be
continued inside the bank network. Do not start changing code immediately.

## Mandatory reading order

Read these files completely before taking implementation actions:

1. `INTRANET_START_HERE.md`
2. `docs/PROJECT_BACKGROUND.md`
3. `docs/TECHNICAL_EXECUTION_SPEC.md`
4. `ARCHITECTURE.md`
5. `docs/DECISION_LOG.md`
6. `docs/INTRANET_AI_HANDOFF.md`
7. The focused integration guide for the current phase:
   - `docs/REAL_LLM_INTEGRATION.md`
   - `docs/REAL_SEMANTIC_ONBOARDING.md`
   - `docs/REAL_OPENSEARCH_MCP_INTEGRATION.md`
8. `docs/INTRANET_EXECUTION_CHECKLIST.md`
9. `INTRANET_PHASE_EXECUTION_PROMPTS.md` for the phase that has been explicitly
   approved by the project owner

After reading, produce an orientation report listing:

- what is confirmed;
- what remains unknown;
- which real internal sources were found;
- which files would change;
- which tests will prove the change.

Do not implement a phase until the required internal source or business answer
exists. Never guess production field meanings, credentials, MCP schemas, carrier
status codes or metric definitions.

## Non-negotiable architecture

- `AnalysisPlan` describes analytical intent and contains no Tool or DSL.
- Tool selection happens after QueryPlan and is deterministic program logic.
- No PPL, Generic OpenSearch API, generic Tool Registry, free LLM Tool loop or
  multi-Agent orchestration.
- Business modules call `OpenSearchGateway`; they do not call MCP tools directly.
- LLMs may create `AnalysisPlan` and summaries only. They do not create executable
  Query DSL, choose tools, calculate metrics or generate HTML/JavaScript.
- Real LLM, Resolver and Validator must share the same injected
  `semantic_compilation`; a model-version mismatch must remain a startup error.
- Metric Engine owns formulas, normalization, denominator and rounding.
- Front end renders structured response values and never recalculates metrics.
- Keep the current FastAPI + Jinja2 + Vanilla JavaScript + local ECharts shape
  unless an explicit approved requirement changes it.

## Frozen business baseline

- Index pattern is `tbl_os_sub_message_YYYY_MM`; July is only the default example.
- Business timezone is `Asia/Hong_Kong`.
- Time intervals are left-closed/right-open `[from,to)`.
- Record count is OpenSearch document count without deduplication.
- `failure_rate.v1` uses normalized `status`:
  - success: `SENT`, `INPROGRESS`;
  - failed: `FAILED`, `ACKFAIL`;
  - everything else, including null/unknown: Other;
  - denominator includes retry and duplicate documents;
  - zero denominator returns null;
  - rounding is `ROUND_HALF_UP` to two decimals.
- `statusCode`/`status_code` is a carrier raw code. Carrier-specific failure rate
  is not defined until internal code tables are supplied.
- A real business definition that differs from v1 creates a new metric version;
  never silently mutate v1.

## Security rules

- `candidate_role` is ignored at CSV import and must never re-enter runtime
  semantics, prompts, field selection, Query DSL or Evidence.
- Blocked fields never enter candidate retrieval, prompts, queries, results,
  charts, summaries or Evidence.
- Mapping-only production fields default to `review_required`.
- The real Catalog is the semantic source of truth; MCP Mapping is automatic
  physical-schema validation, not a second manually maintained semantic table.
- Production Policy/RBAC is an optional productionization track and must remain
  explicitly pending throughout I1-I3.
- Never commit real customer data, credentials, tokens, internal URLs, private
  certificates, raw LLM prompts containing sensitive values or production query
  result dumps.
- Use environment/secret management for runtime credentials. `.env` is ignored.

## Change discipline

- Work one phase at a time.
- Preserve strict Pydantic contracts.
- Add tests before considering a phase complete.
- Golden scenarios must use `POST /api/chat`.
- Run:

```text
python -m pytest -q
python -m ruff check app tests
python -m pyright app tests
node --check app/static/js/app.js
```

- Report files changed, capability added, tests run, result, remaining work and
  next phase after every phase.
