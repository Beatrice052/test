# Contract Gap Checklist

Mark a Contract Gap when the contract does not define:

- exact error body schema
- server clock and timezone basis
- idempotency key retention
- in-progress duplicate request behavior
- payload equality normalization
- authorization failure code
- resource-not-found behavior
- rate limit behavior
- retry-after semantics
- privacy filtering in responses
- pagination or ordering stability
