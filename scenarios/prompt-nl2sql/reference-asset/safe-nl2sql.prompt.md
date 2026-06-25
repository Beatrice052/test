---
name: safe-nl2sql
description: Generate grounded read-only PostgreSQL from a supplied business data dictionary, optional sample rows and reporting question.
argument-hint: "[paste data dictionary, sample rows and question]"
agent: ask
---

# Task

Generate PostgreSQL for the supplied business data dictionary and reporting question.

Input:

Use all content supplied after `/safe-nl2sql` as the input.

If no data dictionary or business question is supplied, ask the user to provide it.

# Rules

Do not use tables or columns not present in the supplied data dictionary.

Treat sample rows as examples for understanding business semantics only. Do not hard-code sample values or produce a query that only works for the sample rows.

Do not silently invent metric definitions.

Do not generate INSERT, UPDATE, DELETE, MERGE, DROP, ALTER, TRUNCATE, GRANT, REVOKE, CREATE, COPY, CALL, or executable administrative statements.

# Method

1. Ground the data dictionary: list tables, relevant columns, likely keys, timestamps, numeric fields and one-to-many relationships.
2. Use sample rows only to clarify edge cases, such as invalid statuses, historical first orders, empty refunds and timezone boundaries.
3. Analyze the request: state output grain, dimensions, metrics, filters, time range, timezone, distinct-count rules, historical lookback, ranking scope, tie-breaking and ambiguities.
4. Design query stages: for each stage state input grain, output grain, filters, joins, aggregations and duplicate-count risk.
5. Generate SQL with inclusive start, exclusive end, explicit timezone handling, safe NULL handling, `NULLIF` for division safety, numeric division, deterministic ordering and CTEs.
6. Self-review against data-dictionary hallucination, write operations, joins, aggregation grain, duplicate counting, historical lookback, time boundary, timezone, NULL, division, Top-N partition and tie-breaking.

# Output

## Data dictionary understanding

## Business interpretation

## Sample-row edge cases

## Ambiguities and assumptions

## Query plan

## Final SQL

## Requirement mapping

| Requirement | SQL evidence | Status |
|---|---|---|

Status must be one of: Satisfied, Partially satisfied, Assumption required, Not satisfied.

## Self-review
