# Risk And Gap Checklist

Use this reference to avoid inventing behavior while still surfacing important tests.

## API Risk Areas

Cover these when the contract exposes relevant behavior:

- authentication header missing, malformed or expired
- authorization denied for a valid authenticated user
- input validation and type coercion
- amount, currency, precision and rounding
- business-rule conflict
- insufficient balance or quota
- response status code and response body schema
- idempotent retry with same key and same payload
- idempotency conflict with same key and different payload
- concurrent submissions using the same idempotency key
- client timeout followed by retry
- privacy leakage in error messages
- auditability of state-changing operations

## Contract Gaps

Record a Contract Gap instead of guessing when the contract omits:

- error response body schema
- exact error codes for each validation failure
- case sensitivity for enum values
- accepted timestamp format and timezone normalization
- server clock source for "now"
- definition of "same request body" for idempotency
- idempotency key retention period
- behavior for in-progress duplicate requests
- behavior for blank or whitespace-only idempotency keys
- numeric coercion, scientific notation or stringified numbers
- rounding behavior for excess decimal places
- authorization error status when authentication is valid

Blocked tests must name the specific gap that blocks expected-result certainty.
