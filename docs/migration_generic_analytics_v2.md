# V6.1 → Generic Analytics / Evidence v2 Migration

## Code and database

Deploy the new application and regenerated schemas/types together. No relational migration is needed: new Evidence metadata is part of `AnswerSnapshot` JSON, and raw/statistical content is stored below `APP_ARTIFACT_DIR/evidence`. Back up database, checkpoints and artifact directory before rollout.

Old snapshots continue to parse because new fields default safely. New clients should prefer `source_queries`, `source_results`, `calculated_tables`, `technical_definitions`, `claim_trace` and `quality_summary`. Do not use legacy `business.quality` for rendering.

## Semantic package

Recompile from approved input. Add Measure/Entity directories as needed. For any Metric formula using `filtered_count`, add versioned `value_dictionary_ids` and explicit `source_field_ids`; compilation requires exactly one compatible dictionary. Follow `docs/internal_handoff/03_SEMANTIC_PACKAGE_BUILD_AND_MIGRATION.md`.

## MCP smoke automation

Replace:

```text
--channel-field <field> --status-field <field>
```

with one to three repeatable generic arguments:

```text
--dimension-field <field-a> --dimension-field <field-b>
```

PowerShell callers use `-DimensionField @('field-a','field-b')`.

## Frontend/API

Regenerate OpenAPI/types with `python scripts/generate_frontend_types.py`. The Drawer paginates `/datasets/{object_id}/rows`, downloads full CSV through the same owner-scoped Dataset endpoint, and downloads raw/statistical JSON through `/answers/{answer_id}/artifacts/{artifact_id}`.

## Rollout

Run Mock verification, deploy to Shadow with a new semantic package version, compare raw/source/calculation/claim hashes, then promote. A package signature change forces requery; do not reuse an older Dataset to answer under a new Metric/Measure/Method definition. Rollback instructions are in `docs/internal_handoff/08_OPERATIONS_TROUBLESHOOTING_AND_ROLLBACK.md`.
