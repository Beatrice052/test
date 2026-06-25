/safe-nl2sql

帮我按下面这些字段写个 SQL，想看 2025 每个月每个城市的客户和金额，最后每个月只要 gmv 最高的 5 个城市，简单解释一下就行。

资料是我自己整理的，可能有点乱，字段就按下面这些用，不用建库。

cities:
city_id 城市 id
city_name 城市名

customers:
customer_id 客户 id
city_id 客户所在城市，对 cities.city_id
created_at 客户创建时间，带时区

orders:
order_id 订单 id
customer_id 下单客户，对 customers.customer_id
status 订单状态
order_amount 订单金额
refund_amount 退款金额，可能空
created_at 下单时间，带时区

城市数据：
1 Taipei
2 Kaohsiung
3 Taichung

客户样例：
101, city 1, 2024-10-02T08:00:00+08:00
102, city 1, 2025-01-03T09:00:00+08:00
103, city 2, 2025-01-10T11:00:00+08:00
104, city 2, 2025-02-01T00:20:00+08:00
105, city 3, 2025-02-05T10:00:00+08:00

订单样例：
9001, customer 101, PAID, amount 100.00, refund 0.00, 2024-12-20T20:00:00+08:00
9002, customer 101, SHIPPED, amount 120.00, refund 20.00, 2025-01-05T10:00:00+08:00
9003, customer 102, PAID, amount 200.00, refund 空, 2025-01-15T12:00:00+08:00
9004, customer 102, CANCELLED, amount 999.00, refund 0.00, 2025-01-16T12:00:00+08:00
9005, customer 103, COMPLETED, amount 80.00, refund 0.00, 2025-01-31T23:30:00+08:00
9006, customer 103, PAID, amount 50.00, refund 空, 2025-02-01T00:30:00+08:00
9007, customer 104, PAID, amount 300.00, refund 30.00, 2025-02-10T16:00:00+08:00
9008, customer 105, FAILED, amount 500.00, refund 0.00, 2025-02-12T09:00:00+08:00
9009, customer 105, COMPLETED, amount 260.00, refund 10.00, 2025-02-20T09:00:00+08:00

我最后要这些列：month, city_id, city_name, active_customers, new_customers, repeat_customers, repeat_rate, net_gmv。

有效订单先算 PAID / SHIPPED / COMPLETED，CANCELLED 和 FAILED 不算。active customers 就是当月有有效订单的人数。new customers 是第一次有效订单就在这个月的人。repeat customers 是这个月有有效订单，而且这个月之前也买过的人。net gmv 是 order_amount 减 refund_amount，refund 空就当 0。repeat rate 是 repeat customers 除以 active customers。月份按 Asia/Taipei 算，gmv 一样的话 city_id 小的排前面。
