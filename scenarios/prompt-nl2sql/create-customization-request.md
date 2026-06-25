/create-prompt

Create a workspace prompt named "safe-nl2sql".

This prompt is for business users and ordinary developers who ask for SQL using data dictionary files that already exist in the workspace or are attached to the current chat.

At runtime, the user should only need to invoke `/safe-nl2sql` and type a short natural-language reporting question. Do not require the user to paste database schema, sample rows, prompt-engineering instructions, checklists, or output templates into the runtime request.

The prompt must:

1. generate read-only PostgreSQL only;
2. use only tables and columns found in the available workspace/chat data context;
3. if the data context is missing, ask the user to attach or open the relevant data dictionary instead of inventing schema;
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
17. treat sample rows as examples for understanding only, not as rows to hard-code into the answer.

The prompt should be especially careful with:

- order-to-item, order-to-payment and order-to-refund one-to-many joins;
- order-level refund allocation to item category;
- full-history first-purchase logic for new versus repeat customers;
- excluding test/internal customers and excluded product types;
- currency conversion through an FX table rather than hard-coded rates.

Use Ask mode and do not pin a model.

Save it as a Workspace prompt.
