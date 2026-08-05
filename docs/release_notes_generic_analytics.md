# Generic Analytics Upgrade Release Notes

Release date: 2026-08-05

Target branch: `MI-GENERIC-ANALYTICS`

## Outcome

The governed V6.1 architecture is preserved while the analytics path becomes Schema/Registry driven. Representative messaging fields remain Mock Golden fixtures, not product routing rules. A previously unknown numeric field and entity are onboarded through semantic configuration, and physically different mappings are proven semantically equivalent.

## Compatibility

- Existing V6.1 AnalysisPlan/QueryPlan/Dataset/Evidence snapshot fields remain readable; new measure/entity/evidence fields have safe defaults.
- Evidence schema version is `2.0`. Legacy `BusinessEvidence.quality` remains present but is always empty in new answers; consumers must use `quality_summary`.
- Existing dataset CSV endpoints remain valid. New raw/statistical JSON downloads use the answer-scoped artifact endpoint.
- MCP smoke CLI changed from representative field arguments to repeatable `--dimension-field`; automation must migrate as described in `docs/migration_generic_analytics_v2.md`.
- No database schema migration is required. Existing AnswerSnapshot JSON persists unchanged; new artifact content resides under `APP_ARTIFACT_DIR/evidence`.

## Deployment prerequisites

Use Node 22.17.0 and Python 3.12, run the full package verifier, compile an approved non-Mock semantic package, pass real LLM/MCP cutover/probes, and complete Shadow/UAT with business, data and security Owner verdicts. The external environment did not contain real credentials/data or Docker, so those production gates remain explicitly internal.

The internal entry point is `docs/internal_handoff/00_START_HERE.md`.
