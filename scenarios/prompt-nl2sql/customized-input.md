/safe-nl2sql

根据下面的数据说明、样例数据和报表需求，帮我写一条 PostgreSQL 查询，顺便简单解释一下。

## 数据说明

假设有 3 张业务表。下面只是测试用的数据字典，不是建表语句，也不需要真实数据库。

### `cities`

| 字段 | 含义 |
|---|---|
| `city_id` | 城市 ID，唯一 |
| `city_name` | 城市名称 |

### `customers`

| 字段 | 含义 |
|---|---|
| `customer_id` | 客户 ID，唯一 |
| `city_id` | 客户所属城市，对应 `cities.city_id` |
| `created_at` | 客户创建时间，带时区时间戳 |

### `orders`

| 字段 | 含义 |
|---|---|
| `order_id` | 订单 ID，唯一 |
| `customer_id` | 下单客户，对应 `customers.customer_id` |
| `status` | 订单状态 |
| `order_amount` | 订单金额 |
| `refund_amount` | 退款金额，可能为空 |
| `created_at` | 订单创建时间，带时区时间戳 |

## 样例数据

### `cities`

| city_id | city_name |
|---:|---|
| 1 | Taipei |
| 2 | Kaohsiung |
| 3 | Taichung |

### `customers`

| customer_id | city_id | created_at |
|---:|---:|---|
| 101 | 1 | 2024-10-02T08:00:00+08:00 |
| 102 | 1 | 2025-01-03T09:00:00+08:00 |
| 103 | 2 | 2025-01-10T11:00:00+08:00 |
| 104 | 2 | 2025-02-01T00:20:00+08:00 |
| 105 | 3 | 2025-02-05T10:00:00+08:00 |

### `orders`

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

## 报表需求

请统计 2025 年每个月、每个城市的 Active customers、New customers、Repeat customers、Net GMV、Repeat rate。

Active customers：
当月至少有一笔有效订单的客户数。

New customers：
客户的第一笔有效订单发生在当月。

Repeat customers：
客户当月有有效订单，并且在当月之前已经有过至少一笔有效订单。

Net GMV：
`SUM(order_amount - COALESCE(refund_amount, 0))`。

Repeat rate：
`repeat_customers / active_customers`。

有效订单状态为 `PAID`、`SHIPPED`、`COMPLETED`。时间按 `Asia/Taipei` 时区划分月份。每个月只返回 Net GMV 最高的五个城市，如果 Net GMV 相同，按照 `city_id` 升序排列。

输出：`month`、`city_id`、`city_name`、`active_customers`、`new_customers`、`repeat_customers`、`repeat_rate`、`net_gmv`。
