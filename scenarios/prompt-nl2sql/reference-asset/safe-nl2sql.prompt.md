---
name: safe-nl2sql
description: Generate grounded read-only PostgreSQL from a business question using available workspace or chat database context.
argument-hint: "[reporting question, optionally with rough table/field reminders]"
agent: ask
---

# Task

Generate read-only PostgreSQL for the user's natural-language reporting question using the available workspace or chat context, such as database context files, data dictionaries, schema notes or business metric documentation.

The user may include a rough reminder of related table names and fields, but should not need to paste the full database documentation into the command. Use all content supplied after `/safe-nl2sql` as the reporting request, then ground the answer in the relevant context that is already open, attached or available in the chat.

If the reporting request or the data context is missing, ask the user to provide or attach the missing information. Do not invent tables, columns, metric definitions or business rules.

# Rules

Do not use tables or columns that are not present in the available data context.

Do not hard-code example IDs, example dates, market codes, categories, currencies or rates unless the business rule explicitly requires them.

Do not silently invent metric definitions. When the context is ambiguous, state the ambiguity and make only clearly labeled assumptions.

Do not generate INSERT, UPDATE, DELETE, MERGE, DROP, ALTER, TRUNCATE, GRANT, REVOKE, CREATE, COPY, CALL, or executable administrative statements.

# Method

1. Identify the data context used: list the context files or pasted sections, relevant tables, relevant columns, keys, timestamps, numeric fields, status fields and business timezones.
2. Ground the request: state output grain, dimensions, metrics, filters, time range, timezone, currency conversion rules, distinct-count rules, historical lookback, ranking scope, tie-breaking and ambiguities.
3. Inspect join cardinality before writing SQL, especially one-to-many joins between orders, items, payments and refunds.
4. Design CTE stages with explicit input grain and output grain for each stage.
5. Aggregate one-to-many tables before joining when needed to avoid duplicate revenue, duplicate refunds or duplicate customers.
6. Use inclusive start and exclusive end for time ranges.
7. Apply business timezone before date truncation, local-date grouping or FX-date joins.
8. Use safe NULL handling, `NULLIF` for division safety, numeric division and deterministic ordering.
9. For customer metrics, use distinct customers and full-history lookback when the definition requires first purchase or repeat behavior.
10. For Top N logic, partition by the requested reporting grain, not globally.
11. Self-review against data-context hallucination, write operations, join duplication, aggregation grain, historical lookback, time boundary, timezone, FX conversion, NULL, division, Top-N partition and tie-breaking.

# Output

## Data context used

## Business interpretation

## Ambiguities and assumptions

## Query plan

## Final SQL

## Requirement mapping

| Requirement | SQL evidence | Status |
|---|---|---|

Status must be one of: Satisfied, Partially satisfied, Assumption required, Not satisfied.

## Self-review
