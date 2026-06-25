/api-contract-test-design

根据下面这个 API 规格帮我写测试用例，尽量写全一点，输出表格。

```text
Endpoint:
POST /v1/payments

Headers:
Authorization: Bearer token
Idempotency-Key: required, maximum 64 characters

Request body:
{
  "sourceAccountId": "string",
  "destinationAccountId": "string",
  "amount": 100.00,
  "currency": "HKD",
  "scheduledAt": "2026-07-01T10:00:00+08:00",
  "note": "string"
}

Rules:

1. sourceAccountId and destinationAccountId are required.
2. The two account IDs cannot be the same.
3. amount must be greater than or equal to 0.01.
4. amount must not exceed 1,000,000.00.
5. amount supports at most two decimal places.
6. currency only supports HKD, CNY, and USD.
7. scheduledAt is optional.
8. If provided, scheduledAt cannot be in the past.
9. scheduledAt cannot be more than 30 days in the future.
10. note is optional and cannot exceed 200 characters.
11. The authenticated user must have permission to use the source account.
12. If the same Idempotency-Key and same request body are submitted again, the API returns the original payment result.
13. If the same Idempotency-Key is used with a different request body, the API returns HTTP 409.
14. Insufficient balance returns HTTP 422.
15. A successful new request returns HTTP 201.

Response:
{
  "paymentId": "string",
  "status": "PENDING",
  "createdAt": "timestamp"
}
```
