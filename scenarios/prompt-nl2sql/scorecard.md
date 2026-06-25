# Scorecard: Prompt NL2SQL

人工填写 A 与 C 的分数和证据。建议每组独立运行 3 次后再计算平均值。

| 检查项 | 评分标准 | A Baseline 分数/证据 | C Customization 分数/证据 | C-A |
|---|---|---|---|---|
| 只使用数据字典字段 | 0=使用不存在表/字段；1=少量可修正引用问题；2=只使用数据字典中的表字段 |  |  |  |
| 不把样例数据写死 | 0=SQL 只适用于样例行或硬编码样例 ID；1=少量硬编码风险；2=样例只用于理解口径 |  |  |  |
| 只读 SQL | 0=包含写操作或管理语句；2=只读查询 |  |  |  |
| 时间边界 | 0=缺失或错误；1=只写 2025 但边界不清；2=使用 2025-01-01 包含、2026-01-01 不包含 |  |  |  |
| 时区处理 | 0=未处理；1=提到但顺序不清；2=按月聚合前应用 `Asia/Taipei` |  |  |  |
| 有效订单过滤 | 0=缺失；1=部分使用；2=只统计 `PAID`、`SHIPPED`、`COMPLETED`，排除样例中的 `CANCELLED`、`FAILED` |  |  |  |
| 首购历史 | 0=只看 2025；1=不确定；3=首笔有效订单考虑完整历史，例如客户 101 在 2025 年 1 月应为 repeat |  |  |  |
| 客户月粒度去重 | 0=订单数误当客户数；1=部分去重；3=客户月粒度正确 |  |  |  |
| New/Repeat 定义 | 0=定义错误；1=部分正确；3=互斥且符合题意 |  |  |  |
| Net GMV | 0=未处理空退款；1=公式部分正确；2=正确使用 `COALESCE(refund_amount, 0)` |  |  |  |
| Repeat rate | 0=可能除零或整数除法；1=处理其一；2=同时避免除零和整数除法 |  |  |  |
| 每月独立 Top 5 | 0=全局 Top 5；1=分区不清；3=按月独立 Top 5 |  |  |  |
| Tie-break | 0=缺失；2=`net_gmv DESC, city_id ASC` 或等价稳定排序 |  |  |  |
| 可审核性 | 0=只有 SQL；1=有少量解释；2=有需求映射或自检 |  |  |  |
| 总分 | 满分 32 |  |  |  |

## Critical Miss

如果漏掉任何 Critical Miss，需要在 Result Summary 单独记录，不能被其他低价值分数掩盖。

- 首购历史考虑完整历史
- `Asia/Taipei` 时区
- 客户月粒度去重
- 每月独立 Top 5

## Result Summary

- A Total:
- C Total:
- Maximum Score: 32
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

- 本场景没有真实数据库，不能因为 SQL “可执行性未知”而扣分；重点看字段约束、口径和可审核性。
- 不能因为输出文字更长就给高分。
- 无法确定的语义点应写入证据，不要猜测。
- C 组如果引入新错误，应在备注中单独记录。
