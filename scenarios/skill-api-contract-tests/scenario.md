# Skill: API Contract 测试用例设计

## 测试目的

验证当普通开发者只说“帮我把测试用例写全一点”时，Workspace Skill 是否能稳定产出覆盖边界、权限、幂等、错误响应和 Contract Gap 的 API 测试设计。

两组对比：

- A：Baseline，普通开发者直接使用默认 Copilot Chat。
- C：Customization，普通开发者使用团队创建好的 `/api-contract-test-design` Skill。

## 测试材料

### API Contract

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

## 正确性检查点

1. 15 条显式业务规则都有 Requirement ID。
2. Header 规则单独覆盖，包括 Authorization 和 Idempotency-Key。
3. Response Schema 被测试，包括 `paymentId`、`status`、`createdAt`。
4. amount 覆盖缺失、NULL、非数字、0、0.009、0.01、正常值、1,000,000.00、1,000,000.01、负数、三位小数。
5. 科学计数法等规格未定义行为标记为 Contract Gap，而不是擅自断言。
6. currency 覆盖 HKD、CNY、USD、小写、未知枚举、空字符串、NULL。
7. account 覆盖 source 缺失、destination 缺失、两者相同、无 source account 权限。
8. scheduledAt 覆盖缺失、NULL、过去、当前时刻、刚晚于当前、恰好 30 天、超过 30 天、不同时区 offset。
9. note 覆盖缺失、NULL、空字符串、长度 1、长度 200、长度 201、Unicode、控制字符。
10. 区分 Authentication 和 Authorization，不把 401 与 403 随意等同。
11. Idempotency 覆盖同 Key 同 Payload、同 Key 不同 Payload、并发、客户端超时重试、不同用户、Key 为空、Key 64、Key 65。
12. 明确列出 Contract Gap，例如错误 Body Schema、server clock、payload 相同的规范化方式、Key 保留时间、in-progress 重复请求。
13. 每个测试用例包含 Test Case ID、优先级、关联需求、前置条件、输入、步骤、预期结果、测试类型。
14. 包含 Requirement Traceability 和 Automation Candidate。
