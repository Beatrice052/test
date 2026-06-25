/create-prompt

Create a workspace prompt named "safe-nl2sql".

This prompt is for business users and ordinary developers who paste a business data dictionary, optional sample rows, and a natural-language reporting question.

At runtime, the user should only need to invoke `/safe-nl2sql` and paste the input. Do not require the user to know prompt engineering.

The prompt must:

1. generate read-only PostgreSQL only;
2. use only supplied tables and columns;
3. identify output grain before writing SQL;
4. extract exact metric definitions;
5. identify joins and one-to-many duplication risks;
6. distinguish row counts from distinct entity counts;
7. use inclusive start and exclusive end for time ranges;
8. apply the requested timezone before date truncation or grouping;
9. handle NULL, division by zero and decimal precision;
10. verify ranking scope and deterministic tie-breaking;
11. identify ambiguity instead of silently inventing business rules;
12. organize complex SQL into understandable stages;
13. map every requirement to SQL evidence;
14. perform a final self-review;
15. answer in Chinese;
16. accept a different data dictionary, sample data and question on every run;
17. treat sample rows as examples for understanding only, not as rows to hard-code into the answer.

Use Ask mode and do not pin a model.

Save it as a Workspace prompt.
