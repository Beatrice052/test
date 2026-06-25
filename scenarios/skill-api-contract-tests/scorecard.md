# Scorecard: API Contract 测试用例设计

人工填写 A 与 C 的分数和证据。建议每组独立运行 3 次后再计算平均值。

| 检查项 | 评分标准 | A Baseline 分数/证据 | C Customization 分数/证据 | C-A |
|---|---|---|---|---|
| Requirement ID | 0=没有需求编号；2=部分编号；4=15 条规则完整编号 |  |  |  |
| Test Case ID | 0=无稳定 ID；3=每个用例有稳定 ID |  |  |  |
| 优先级 | 0=无优先级；1=只有一种；3=包含 P0/P1/P2 |  |  |  |
| Amount 上下边界 | 0=少量正常用例；2=覆盖部分边界；5=覆盖缺失、NULL、类型、最小/最大、越界、精度 |  |  |  |
| Currency 枚举 | 0=只测正常；1=部分异常；3=正常枚举和非法枚举完整 |  |  |  |
| Account 规则 | 0=遗漏；2=覆盖必填和相同账户；3=包含 source 权限 |  |  |  |
| scheduledAt 时间边界 | 0=遗漏；2=部分覆盖；4=覆盖过去、当前、刚未来、30 天、时区和 Gap |  |  |  |
| note 边界 | 0=遗漏；1=只测长度；3=覆盖 NULL、空、边界长度、Unicode、控制字符 |  |  |  |
| Authentication / Authorization | 0=混淆；1=部分区分；3=明确区分 401、403 和 source account 权限 |  |  |  |
| Idempotency | 0=遗漏；2=只测重复；5=覆盖同 payload、不同 payload、并发、超时重试、不同用户、Key 边界 |  |  |  |
| Contract Gap | 0=把未定义行为当确定预期；1=少量 Gap；3=明确列出关键 Gap |  |  |  |
| Response/Error Schema | 0=遗漏；1=只测成功响应；3=成功和错误响应都覆盖，未定义错误体标 Gap |  |  |  |
| Traceability | 0=无追踪；3=需求到用例可追踪 |  |  |  |
| Automation Candidate | 0=无；2=标记自动化候选 |  |  |  |
| 总分 | 满分 47 |  |  |  |

## Critical Miss

如果漏掉任何 Critical Miss，需要在 Result Summary 单独记录，不能被其他低价值分数掩盖。

- Amount 上下边界
- Authentication / Authorization
- Idempotency
- Contract Gap

## Result Summary

- A Total:
- C Total:
- Maximum Score: 47
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

- 未定义行为必须记为 Contract Gap。
- 不要把“表格很多”当成覆盖充分。
- C 组如果输出僵化或机械复用错误模板，应单独记录。
