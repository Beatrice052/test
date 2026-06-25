# Prompt: NL2SQL

## 测试目的

验证在 Workspace 已经存在数据库说明的情况下，普通用户用一段不专业但包含基本表名/字段线索的自然语言请求做 NL2SQL，团队创建好的 Workspace Prompt `/safe-nl2sql` 是否能比默认 Copilot 更稳定地产出可审核、只读、基于真实字段的 PostgreSQL。

这个场景不需要真实数据库，也不要求本地执行 SQL。`workspace-context/ecommerce_database.md` 模拟项目里本来就存在的数据库说明文件。A 组和 C 组都必须使用同一个 Workspace context；差异只允许是 C 组在同一段用户输入前多加 `/safe-nl2sql`。

对比组：

- A：Baseline，普通用户使用默认 Copilot Chat，复制 `novice-input.md`。
- C：Customization，普通用户使用团队创建好的 `/safe-nl2sql` Prompt File，复制 `customized-input.md`。

注意：`/create-prompt` 只用于创建 Prompt File，不是 C 组运行时输入。C 组运行时使用的是 `/safe-nl2sql`。

## 测试材料

- Existing workspace database context: `workspace-context/ecommerce_database.md`
- A 组用户输入: `novice-input.md`
- C 组用户输入: `customized-input.md`
- Prompt 创建请求: `create-customization-request.md`
- 参考 Prompt File: `reference-asset/safe-nl2sql.prompt.md`
- 人工评分卡: `scorecard.md`

## 用户任务

用户要生成 PostgreSQL，用于统计 2026 Q2 每个月、每个市场内销售额最高的 3 个商品品类，并输出客户数、新客、老客、gross/refund/net revenue USD、refund rate 和 repeat rate。

用户输入应当像真实业务人员或普通开发者：会写出大概有哪些表、常用字段和业务口径，但不会提供完整 SQL 设计步骤、专业检查清单、CTE 方案、join 去重策略或自检模板。

## 正确性检查点

1. 使用 `workspace-context/ecommerce_database.md` 中存在的表和字段，不编造表字段。
2. 生成只读 PostgreSQL，不包含写操作或管理语句。
3. 不要求用户再提供真实数据库、建表语句或样例数据。
4. 使用 2026-04-01 起点包含、2026-07-01 终点不包含的 Q2 时间范围。
5. 月份和汇率日期必须先转换到 `dim_market.business_timezone` 对应的本地时间。
6. 有效订单同时满足有效 `order_status` 和 `CAPTURED` 支付。
7. 排除测试客户、`INTERNAL` 客户和 gift card 商品。
8. 按订单明细计算品类收入，不把订单级金额重复摊到每个明细。
9. `fact_order_item`、`fact_payment`、`fact_refund` 都是一对多风险来源，SQL 需要避免重复聚合。
10. 退款只统计 `SUCCEEDED`，并按订单内非 gift card 品类收入占比分摊。
11. 退款按退款成功月份扣减，而不是按原订单月份扣减。
12. USD 转换使用 `daily_fx_rate`，不硬编码汇率。
13. New/Repeat customer 判断使用当前统计期之前的完整历史首购，不只看 Q2。
14. 客户数使用去重客户数，不把订单数或明细数误当客户数。
15. Repeat rate 和 refund rate 避免整数除法和除零。
16. Top 3 按每个本地月份、每个市场独立排名，并用 `category ASC` 处理并列。
17. 输出包含查询计划、需求映射或自检，便于人工审核。
