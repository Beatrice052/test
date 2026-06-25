# Scorecard: Prompt NL2SQL

人工填写 A 和 C 的分数和证据。建议每组独立运行 3 次后再计算平均值。

| 检查项 | 评分标准 | A Baseline 分数/证据 | C Customization 分数/证据 | C-A |
|---|---|---|---|---|
| 使用用户提供的 schema | 0=编造 schema 或要求重新提供完整数据库文档；1=部分引用用户输入；2=正确基于 `novice-input.md/customized-input.md` 的表、字段和口径 |  |  |  |
| 只使用数据字典字段 | 0=使用不存在表/字段；1=少量可修正引用问题；2=只使用场景中定义的表字段 |  |  |  |
| 不硬编码业务值 | 0=硬编码示例 ID/日期/品类/汇率导致 SQL 不通用；1=少量硬编码风险；2=除业务规则常量外不硬编码 |  |  |  |
| 只读 SQL | 0=包含写操作或管理语句；1=只读查询 |  |  |  |
| Q2 时间边界 | 0=缺失或错误；1=只写 Q2 但边界不清；2=使用 `2026-04-01` 包含、`2026-07-01` 不包含 |  |  |  |
| 市场本地时区 | 0=未处理；1=使用固定时区或顺序不清；3=按 `dim_market.business_timezone` 在月分组和本地日期前转换 |  |  |  |
| 有效订单和支付 | 0=只看订单状态或只看支付；1=部分正确；3=同时要求有效 `order_status` 和 `CAPTURED` 支付 |  |  |  |
| 排除范围 | 0=未排除；1=只排除一部分；2=排除测试客户、`INTERNAL` 客户和 gift card 明细 |  |  |  |
| 多表一对多去重 | 0=直接展开订单、明细、支付、退款导致重复；2=部分预聚合；4=明确按正确粒度预聚合或用 CTE 避免重复计算 |  |  |  |
| 退款处理 | 0=漏掉退款或重复扣减；2=只按订单扣减但品类分摊不清；4=只统计 `SUCCEEDED`，按非礼品卡品类收入占比分摊，并按退款月份扣减 |  |  |  |
| FX 转换 | 0=未转换或硬编码汇率；1=提到汇率但 join 不清；2=用 `daily_fx_rate` 按币种和市场本地日期转换 gross/refund/net USD |  |  |  |
| New/Repeat 历史口径 | 0=只看 Q2；2=部分考虑历史；4=基于完整历史首个有效非礼品卡订单判断 new/repeat |  |  |  |
| 客户数去重 | 0=把订单/明细数当客户数；1=部分去重；2=按客户去重计算 paying/new/repeat customers |  |  |  |
| Rate 安全性 | 0=可能除零或整数除法；1=处理其一；2=repeat/refund rate 都避免除零并保持小数 |  |  |  |
| 每月每市场 Top 3 | 0=全局 Top 3；1=分区不完整；2=按 month + market 独立 Top 3 |  |  |  |
| Tie-break | 0=缺失；1=使用 `net_revenue_usd DESC, category ASC` 或等价稳定排序 |  |  |  |
| 可审核性 | 0=只有 SQL；1=有少量解释；2=有查询计划、需求映射或自检 |  |  |  |
| 总分 | 满分 40 |  |  |  |

## Critical Miss

如果漏掉任何 Critical Miss，需要在 Result Summary 单独记录，不能被其他低价值分数掩盖。

- 没有使用用户输入中的 schema，或要求用户重新粘贴完整数据库文档
- 多表一对多 join 导致收入、退款或客户数重复
- New/Repeat 只看 Q2，没有完整历史首购
- 没有按市场本地时区分月
- 没有正确处理订单级退款到品类的分摊

## Result Summary

- A Total:
- C Total:
- Maximum Score: 40
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

- 本场景没有真实数据库，不能因为 SQL “可执行性未知”而扣分；重点看字段约束、业务口径和可审核性。
- 不能因为输出文字更长就给高分。
- 无法确定的语义点应写入证据，不要猜测。
- C 组如果引入新错误，应在备注中单独记录。
