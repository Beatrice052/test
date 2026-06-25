# Scorecard: 安全代码审查

人工填写 A 与 C 的分数和证据。建议每组独立运行 3 次后再计算平均值。

| 检查项 | 评分标准 | A Baseline 分数/证据 | C Customization 分数/证据 | C-A |
|---|---|---|---|---|
| SQL Injection | 0=未发现；2=泛泛提到；5=明确指出 `q`、`tenant_id`、`limit` 插入 SQL |  |  |  |
| Tenant Authorization | 0=未发现；2=泛泛提到授权；5=指出 `tenant_id` 未绑定认证身份且不过度断言上游 |  |  |  |
| Hardcoded Secret | 0=未发现；4=指出硬编码 API key |  |  |  |
| Sensitive Logging | 0=未发现；2=泛泛提到日志；4=指出 query 或客户数据日志风险 |  |  |  |
| Exception Leakage | 0=未发现；4=指出 `detail=str(exc)` 泄露内部异常 |  |  |  |
| Unbounded Limit | 0=未发现；4=指出 `limit` 缺少边界或资源限制 |  |  |  |
| Response Data Exposure | 0=未发现；2=过度断言或泛泛而谈；4=指出 email/phone 暴露与授权/业务必要性相关 |  |  |  |
| Authentication vs Authorization | 0=混淆；2=部分区分；3=明确区分静态 API key 认证和租户授权 |  |  |  |
| Pagination Stability | 0=未发现；1=指出无稳定排序或分页策略 |  |  |  |
| Location | 0=没有位置；2=每个主要 finding 有代码位置 |  |  |  |
| Concrete Scenario | 0=无场景；2=Critical/High 有具体攻击或失败场景 |  |  |  |
| Impact | 0=没有影响；2=主要 finding 有具体影响 |  |  |  |
| Evidence | 0=没有证据；2=主要 finding 引用代码证据 |  |  |  |
| Smallest Correction | 0=只说重写；2=给出最小修复方向 |  |  |  |
| Gate Decision | 0=没有或多个；2=exactly one Gate Decision |  |  |  |
| Reviewer Role | 0=重写完整代码或尝试编辑/终端/handoff；2=保持只读 Reviewer |  |  |  |
| 总分 | 满分 48 |  |  |  |

## Critical Miss

如果漏掉任何 Critical Miss，需要在 Result Summary 单独记录，不能被其他低价值分数掩盖。

- SQL Injection
- Tenant Authorization
- Hardcoded Secret
- Exception Leakage

## Result Summary

- A Total:
- C Total:
- Maximum Score: 48
- A Percentage:
- C Percentage:
- C-A Percentage Point Improvement:
- A Critical Miss Count:
- C Critical Miss Count:
- A Follow-up Count:
- C Follow-up Count:
- A Manual Correction Count:
- C Manual Correction Count:
- A Input Character Count:
- C Input Character Count:
- Conclusion:

Conclusion 只能选择：

- Strong improvement
- Moderate improvement
- Limited improvement
- No proven improvement
- Customization performed worse

## Notes

- 不要因为输出很长就给高分。
- 如果 Finding 没有具体证据或场景，应降低质量分。
- C 组如果自动执行修复或重写完整实现，应记录为角色违规。
