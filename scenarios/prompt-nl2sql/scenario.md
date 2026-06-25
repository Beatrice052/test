# Prompt: NL2SQL

## 测试目的

验证在数据字典和少量样例数据已经存在于 Workspace 的情况下，普通用户只输入一个自然语言查询需求时，团队创建好的 Workspace Prompt `/safe-nl2sql` 是否能比默认 Copilot 更稳定地生成可审核、只读、基于真实字段的 PostgreSQL。

本场景不需要真实数据库，也不要求本地执行 SQL。`scenario.md` 模拟项目中已有的数据说明文件。运行 A 组和 C 组时，测试人员应把本文件作为相同的 Workspace/Chat context 提供给 Copilot，但不要把下面的数据字典和样例行复制进 `novice-input.md` 或 `customized-input.md`。

对比组：

- A：Baseline，普通用户使用默认 Copilot Chat，只输入一个粗糙查询请求。
- C：Customization，普通用户使用团队创建好的 `/safe-nl2sql` Prompt File，只在同一个请求前多加 Slash Command。

## Workspace 数据上下文

下面是公司电商数仓中与本测试相关的数据说明。它不是建表语句，只是 Copilot 在生成 SQL 时可参考的现有项目资料。

### 业务背景

公司有多个市场，每个市场有自己的业务时区。报表通常按市场本地时间统计。订单、支付、退款、商品明细是分表存储的，存在一对多关系。不能直接把订单、明细、退款、支付全部展开后聚合，否则会重复计算收入或退款。

金额字段保存为订单原币种。需要输出 USD 指标时，必须使用 `daily_fx_rate` 按本地日期和币种转换，不要硬编码汇率。

### `dim_market`

| 字段 | 含义 |
|---|---|
| `market_code` | 市场代码，唯一，例如 `TW`、`HK`、`SG` |
| `market_name` | 市场名称 |
| `business_timezone` | 市场业务时区，例如 `Asia/Taipei`、`Asia/Hong_Kong`、`Asia/Singapore` |

### `dim_customer`

| 字段 | 含义 |
|---|---|
| `customer_id` | 客户 ID，唯一 |
| `market_code` | 客户所属市场，对应 `dim_market.market_code` |
| `created_at` | 客户创建时间，`timestamptz` |
| `customer_type` | 客户类型，`NORMAL`、`VIP`、`INTERNAL` |
| `is_test_customer` | 是否测试客户 |

### `dim_product`

| 字段 | 含义 |
|---|---|
| `product_id` | 商品 ID，唯一 |
| `category` | 商品一级品类 |
| `is_gift_card` | 是否礼品卡商品 |

### `fact_order`

| 字段 | 含义 |
|---|---|
| `order_id` | 订单 ID，唯一 |
| `customer_id` | 下单客户，对应 `dim_customer.customer_id` |
| `market_code` | 订单市场，对应 `dim_market.market_code` |
| `order_status` | 订单状态，可能值包括 `CREATED`、`PAID`、`SHIPPED`、`COMPLETED`、`CANCELLED`、`FAILED` |
| `ordered_at` | 下单时间，`timestamptz` |
| `currency` | 订单币种，例如 `TWD`、`HKD`、`SGD`、`USD` |

### `fact_order_item`

| 字段 | 含义 |
|---|---|
| `order_item_id` | 订单明细 ID，唯一 |
| `order_id` | 所属订单，对应 `fact_order.order_id` |
| `product_id` | 商品，对应 `dim_product.product_id` |
| `quantity` | 数量 |
| `item_gross_amount` | 明细原价金额，订单币种 |
| `item_discount_amount` | 明细折扣金额，订单币种，可能为空 |

### `fact_payment`

| 字段 | 含义 |
|---|---|
| `payment_id` | 支付记录 ID，唯一 |
| `order_id` | 所属订单，对应 `fact_order.order_id` |
| `payment_status` | 支付状态，可能值包括 `AUTHORIZED`、`CAPTURED`、`FAILED`、`REFUNDED` |
| `captured_at` | 支付成功时间，`timestamptz`，失败或仅授权时可能为空 |
| `captured_amount` | 支付成功金额，订单币种 |

### `fact_refund`

| 字段 | 含义 |
|---|---|
| `refund_id` | 退款记录 ID，唯一 |
| `order_id` | 所属订单，对应 `fact_order.order_id` |
| `refund_status` | 退款状态，可能值包括 `REQUESTED`、`SUCCEEDED`、`FAILED` |
| `refunded_at` | 退款成功时间，`timestamptz` |
| `refund_amount` | 退款金额，订单币种 |

### `daily_fx_rate`

| 字段 | 含义 |
|---|---|
| `rate_date` | 汇率日期，按市场本地日期匹配 |
| `currency` | 币种 |
| `usd_rate` | 1 单位原币兑换 USD 的汇率 |

## 业务口径

1. 有效订单：`fact_order.order_status IN ('PAID', 'SHIPPED', 'COMPLETED')`，并且该订单至少有一条 `payment_status = 'CAPTURED'` 的支付记录。
2. 无效订单：`CREATED`、`CANCELLED`、`FAILED` 不计入收入、客户数或首购。
3. 排除客户：`dim_customer.is_test_customer = true` 或 `customer_type = 'INTERNAL'` 的客户不计入。
4. 排除商品：`dim_product.is_gift_card = true` 的明细不计入品类收入或客户数。
5. 明细收入：`item_gross_amount - COALESCE(item_discount_amount, 0)`。
6. 汇率转换：收入使用支付成功时间在市场本地时区对应的本地日期匹配 `daily_fx_rate`；退款使用退款成功时间在市场本地时区对应的本地日期匹配 `daily_fx_rate`。
7. 退款：只统计 `refund_status = 'SUCCEEDED'` 的退款。退款是订单级金额，按该订单中非礼品卡明细的明细收入占比分摊到品类，避免在多品类订单上重复扣减。
8. New paying customers：客户在该市场的第一笔有效非礼品卡订单发生在当前统计月份，并且该客户当月购买了该品类。
9. Repeat paying customers：客户当月购买了该品类，并且在当前月份之前已经有过至少一笔有效非礼品卡订单。
10. Paying customers：当月购买该品类的去重客户数。
11. Repeat rate：`repeat_paying_customers / paying_customers`。
12. Refund rate：`refund_amount_usd / gross_revenue_usd`。
13. Top N：每个本地月份、每个市场内按 `net_revenue_usd` 取 Top 3 品类；并列时按 `category ASC` 稳定排序。

## 样例数据

这些样例行只用于说明边界和人工审核，不代表完整数据集。生成 SQL 时不能硬编码这些 ID 或样例值。

### `dim_market`

| market_code | market_name | business_timezone |
|---|---|---|
| TW | Taiwan | Asia/Taipei |
| HK | Hong Kong | Asia/Hong_Kong |
| SG | Singapore | Asia/Singapore |

### `dim_customer`

| customer_id | market_code | created_at | customer_type | is_test_customer |
|---:|---|---|---|---|
| 101 | TW | 2025-12-20T10:00:00+08:00 | NORMAL | false |
| 102 | TW | 2026-04-03T09:00:00+08:00 | VIP | false |
| 103 | HK | 2026-04-18T12:00:00+08:00 | NORMAL | false |
| 104 | HK | 2026-05-01T00:10:00+08:00 | INTERNAL | false |
| 105 | SG | 2026-05-20T11:00:00+08:00 | NORMAL | true |
| 106 | SG | 2026-03-28T18:00:00+08:00 | NORMAL | false |

### `dim_product`

| product_id | category | is_gift_card |
|---:|---|---|
| 201 | Electronics | false |
| 202 | Beauty | false |
| 203 | Home | false |
| 204 | Gift Card | true |
| 205 | Sports | false |

### `fact_order`

| order_id | customer_id | market_code | order_status | ordered_at | currency |
|---:|---:|---|---|---|---|
| 5001 | 101 | TW | COMPLETED | 2026-03-31T23:40:00+08:00 | TWD |
| 5002 | 101 | TW | SHIPPED | 2026-04-05T09:30:00+08:00 | TWD |
| 5003 | 102 | TW | CANCELLED | 2026-04-08T12:00:00+08:00 | TWD |
| 5004 | 102 | TW | PAID | 2026-04-15T13:00:00+08:00 | TWD |
| 5005 | 103 | HK | COMPLETED | 2026-05-01T00:20:00+08:00 | HKD |
| 5006 | 104 | HK | PAID | 2026-05-10T10:00:00+08:00 | HKD |
| 5007 | 105 | SG | PAID | 2026-05-22T10:00:00+08:00 | SGD |
| 5008 | 106 | SG | PAID | 2026-06-30T23:50:00+08:00 | SGD |
| 5009 | 106 | SG | PAID | 2026-07-01T00:10:00+08:00 | SGD |

### `fact_order_item`

| order_item_id | order_id | product_id | quantity | item_gross_amount | item_discount_amount |
|---:|---:|---:|---:|---:|---:|
| 7001 | 5001 | 201 | 1 | 3000 | 0 |
| 7002 | 5002 | 201 | 1 | 5000 | 500 |
| 7003 | 5002 | 202 | 2 | 2000 |  |
| 7004 | 5003 | 201 | 1 | 8000 | 0 |
| 7005 | 5004 | 204 | 1 | 1000 | 0 |
| 7006 | 5005 | 202 | 1 | 1200 | 100 |
| 7007 | 5005 | 203 | 1 | 800 | 0 |
| 7008 | 5006 | 203 | 1 | 600 | 0 |
| 7009 | 5007 | 205 | 1 | 300 | 0 |
| 7010 | 5008 | 201 | 1 | 900 | 90 |
| 7011 | 5009 | 202 | 1 | 700 | 0 |

### `fact_payment`

| payment_id | order_id | payment_status | captured_at | captured_amount |
|---:|---:|---|---|---:|
| 8001 | 5001 | CAPTURED | 2026-03-31T23:45:00+08:00 | 3000 |
| 8002 | 5002 | CAPTURED | 2026-04-05T09:35:00+08:00 | 6500 |
| 8003 | 5003 | FAILED |  | 0 |
| 8004 | 5004 | CAPTURED | 2026-04-15T13:05:00+08:00 | 1000 |
| 8005 | 5005 | CAPTURED | 2026-05-01T00:25:00+08:00 | 1900 |
| 8006 | 5006 | CAPTURED | 2026-05-10T10:05:00+08:00 | 600 |
| 8007 | 5007 | CAPTURED | 2026-05-22T10:05:00+08:00 | 300 |
| 8008 | 5008 | AUTHORIZED |  | 810 |
| 8009 | 5008 | CAPTURED | 2026-06-30T23:55:00+08:00 | 810 |
| 8010 | 5009 | CAPTURED | 2026-07-01T00:15:00+08:00 | 700 |

### `fact_refund`

| refund_id | order_id | refund_status | refunded_at | refund_amount |
|---:|---:|---|---|---:|
| 9001 | 5002 | SUCCEEDED | 2026-04-20T10:00:00+08:00 | 1300 |
| 9002 | 5005 | FAILED | 2026-05-05T10:00:00+08:00 | 200 |
| 9003 | 5005 | SUCCEEDED | 2026-06-02T11:00:00+08:00 | 300 |

### `daily_fx_rate`

| rate_date | currency | usd_rate |
|---|---|---:|
| 2026-03-31 | TWD | 0.031 |
| 2026-04-05 | TWD | 0.031 |
| 2026-04-20 | TWD | 0.031 |
| 2026-05-01 | HKD | 0.128 |
| 2026-06-02 | HKD | 0.128 |
| 2026-05-22 | SGD | 0.740 |
| 2026-06-30 | SGD | 0.740 |
| 2026-07-01 | SGD | 0.740 |

## 用户查询任务

用户实际输入不包含上面的数据字典和样例行。用户只会表达类似：

```text
老板要看 2026 Q2 每个月、每个市场 top3 品类的收入和客户情况，帮我写个 PostgreSQL。
```

完整的测试输入见 `novice-input.md` 和 `customized-input.md`。

## 正确性检查点

1. 只使用本场景数据字典中存在的表和字段。
2. 生成只读 PostgreSQL，不包含写操作或管理语句。
3. 不要求用户再次粘贴客户、订单或样例数据；如果上下文缺失，应明确要求附加数据说明文件。
4. 使用 2026-04-01 起点包含、2026-07-01 终点不包含的 Q2 时间范围。
5. 月份和汇率日期必须先转换到 `dim_market.business_timezone` 对应的本地时间。
6. 有效订单同时满足有效 `order_status` 和 `CAPTURED` 支付。
7. 排除测试客户、`INTERNAL` 客户和礼品卡商品。
8. 按订单明细计算品类收入，不把订单级金额重复摊到每个明细。
9. 退款只统计 `SUCCEEDED`，并按订单内非礼品卡品类收入占比分摊。
10. 退款按退款成功月份扣减，而不是按原订单月份扣减。
11. USD 转换使用 `daily_fx_rate`，不硬编码汇率。
12. New/Repeat customer 判断使用当前统计期之前的完整历史首购，不只看 Q2。
13. 客户数使用去重客户数，不把订单数或明细数误当客户数。
14. Repeat rate 和 refund rate 避免整数除法和除零。
15. Top 3 按每个本地月份、每个市场独立排名，并用 `category ASC` 处理并列。
16. 输出包含需求映射或自检，便于人工审核。
