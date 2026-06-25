# Prompt: NL2SQL

## 测试目的

验证当普通用户只提供一份业务数据字典、少量样例数据和一个报表问题时，Workspace Prompt File 是否能帮助 GitHub Copilot 更稳定地生成可审查、只读、基于输入字段的 PostgreSQL 查询。

本场景不需要真实数据库，也不要求本地执行 SQL。样例数据只用于帮助人理解业务口径和人工评分。

两组对比：

- A：Baseline，普通用户直接使用默认 Copilot Chat。
- C：Customization，普通用户使用团队创建好的 `/safe-nl2sql` Prompt File。

## 测试材料

### 业务数据字典

假设公司有 3 张业务表。下面只是数据字典，不是建表语句。

#### `cities`

| 字段 | 含义 |
|---|---|
| `city_id` | 城市 ID，唯一 |
| `city_name` | 城市名称 |

#### `customers`

| 字段 | 含义 |
|---|---|
| `customer_id` | 客户 ID，唯一 |
| `city_id` | 客户所属城市，对应 `cities.city_id` |
| `created_at` | 客户创建时间，带时区时间戳 |

#### `orders`

| 字段 | 含义 |
|---|---|
| `order_id` | 订单 ID，唯一 |
| `customer_id` | 下单客户，对应 `customers.customer_id` |
| `status` | 订单状态 |
| `order_amount` | 订单金额 |
| `refund_amount` | 退款金额，可能为空 |
| `created_at` | 订单创建时间，带时区时间戳 |

### 样例数据

这些样例行只用于说明边界，不代表完整数据集。

#### `cities`

| city_id | city_name |
|---:|---|
| 1 | Taipei |
| 2 | Kaohsiung |
| 3 | Taichung |

#### `customers`

| customer_id | city_id | created_at |
|---:|---:|---|
| 101 | 1 | 2024-10-02T08:00:00+08:00 |
| 102 | 1 | 2025-01-03T09:00:00+08:00 |
| 103 | 2 | 2025-01-10T11:00:00+08:00 |
| 104 | 2 | 2025-02-01T00:20:00+08:00 |
| 105 | 3 | 2025-02-05T10:00:00+08:00 |

#### `orders`

| order_id | customer_id | status | order_amount | refund_amount | created_at |
|---:|---:|---|---:|---:|---|
| 9001 | 101 | PAID | 100.00 | 0.00 | 2024-12-20T20:00:00+08:00 |
| 9002 | 101 | SHIPPED | 120.00 | 20.00 | 2025-01-05T10:00:00+08:00 |
| 9003 | 102 | PAID | 200.00 |  | 2025-01-15T12:00:00+08:00 |
| 9004 | 102 | CANCELLED | 999.00 | 0.00 | 2025-01-16T12:00:00+08:00 |
| 9005 | 103 | COMPLETED | 80.00 | 0.00 | 2025-01-31T23:30:00+08:00 |
| 9006 | 103 | PAID | 50.00 |  | 2025-02-01T00:30:00+08:00 |
| 9007 | 104 | PAID | 300.00 | 30.00 | 2025-02-10T16:00:00+08:00 |
| 9008 | 105 | FAILED | 500.00 | 0.00 | 2025-02-12T09:00:00+08:00 |
| 9009 | 105 | COMPLETED | 260.00 | 10.00 | 2025-02-20T09:00:00+08:00 |

### 报表问题

请生成 PostgreSQL 查询，用于统计 2025 年每个月、每个城市的：

1. Active customers：当月至少有一笔有效订单的客户数。
2. New customers：客户的第一笔有效订单发生在当月。
3. Repeat customers：客户当月有有效订单，并且当月之前已经有过至少一笔有效订单。
4. Net GMV：`SUM(order_amount - COALESCE(refund_amount, 0))`。
5. Repeat rate：`repeat_customers / active_customers`。

有效订单状态为 `PAID`、`SHIPPED`、`COMPLETED`。

时间按 `Asia/Taipei` 时区划分月份。

每个月只返回 Net GMV 最高的五个城市。如果 Net GMV 相同，按照 `city_id` 升序排列。

输出：`month`、`city_id`、`city_name`、`active_customers`、`new_customers`、`repeat_customers`、`repeat_rate`、`net_gmv`。

## 样例口径提示

这些提示用于人工审核，不要求 Copilot 直接计算样例结果。

- 客户 101 在 2024 年已经有有效订单，所以 2025 年 1 月应算 Repeat customer，不是 New customer。
- 订单 9004 和 9008 不是有效订单。
- 订单 9003 的 `refund_amount` 为空，Net GMV 应按退款 0 处理。
- 订单 9006 在 `Asia/Taipei` 下属于 2025 年 2 月。
- Top 5 应按每个月分别排名。

## 正确性检查点

1. 只使用数据字典中出现的表和字段。
2. 只生成只读 SQL，不包含写操作或管理语句。
3. 使用 2025-01-01 起点包含、2026-01-01 终点不包含的时间范围。
4. 在按月聚合前正确应用 `Asia/Taipei` 时区。
5. 有效订单过滤条件在首购、活跃、GMV 中一致使用。
6. New customers 的首笔有效订单需要考虑 2025 年之前的历史订单。
7. 每个客户在每个城市月份中只计数一次。
8. New customers 与 Repeat customers 定义互斥且一致。
9. Net GMV 正确处理 `refund_amount` 为空。
10. Repeat rate 避免整数除法和除零。
11. Top 5 按每个月独立计算，不是全局 Top 5。
12. Net GMV 并列时按 `city_id ASC` 稳定排序。
13. 输出包含需求映射或自检，便于人工审核。
