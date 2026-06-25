/create-prompt

Create a workspace prompt named "safe-nl2sql".

This prompt is for business users and ordinary developers who ask for SQL by typing a simplified schema, business rules and a reporting question in the chat. The workspace or chat may also include small CSV/JSON sample data.

At runtime, the user should only need to invoke `/safe-nl2sql` and type a rough NL2SQL request that includes simple table and field information. Do not require the user to write prompt-engineering instructions, checklists, SQL design steps, or output templates.

The prompt must:

1. generate read-only PostgreSQL only;
2. use only tables and columns supplied by the user or visible in attached sample-data metadata;
3. if the schema is missing, ask the user to provide table and field information instead of inventing schema;
4. identify output grain before writing SQL;
5. extract exact metric definitions from the user request and available context;
6. identify joins and one-to-many duplication risks before aggregating;
7. distinguish row counts, order counts, item counts and distinct customer counts;
8. use inclusive start and exclusive end for time ranges;
9. apply the requested business timezone before date truncation, month grouping or local-date FX joins;
10. handle NULL, division by zero and decimal precision;
11. verify ranking scope and deterministic tie-breaking;
12. identify ambiguity instead of silently inventing business rules;
13. organize complex SQL into understandable CTE stages;
14. map every requirement to SQL evidence;
15. perform a final self-review;
16. answer in Chinese;
17. never hard-code example IDs, dates, markets, categories or rates unless the business rule explicitly requires them.

The prompt should be especially careful with:

- order-to-item, order-to-payment and order-to-refund one-to-many joins;
- order-level refund allocation to item category;
- full-history first-purchase logic for new versus repeat customers;
- excluding test/internal customers and excluded product types;
- currency conversion through an FX table rather than hard-coded rates.

Use Ask mode and do not pin a model.

Save it as a Workspace prompt.
