帮我写个 PostgreSQL，看 2026 Q2 每个月、每个 market 里面 net revenue usd 最高的 top 3 category。

我记得 workspace 里有这些表：dim_market(market_code, market_name, business_timezone)，dim_customer(customer_id, market_code, customer_type, is_test_customer)，dim_product(product_id, category, is_gift_card)，fact_order(order_id, customer_id, market_code, order_status, ordered_at, currency)，fact_order_item(order_id, product_id, quantity, item_gross_amount, item_discount_amount)，fact_payment(order_id, payment_status, captured_at, captured_amount)，fact_refund(order_id, refund_status, refunded_at, refund_amount)，daily_fx_rate(rate_date, currency, usd_rate)。

结果想要 month、market_code、market_name、category、paying_customers、new_paying_customers、repeat_paying_customers、gross_revenue_usd、refund_amount_usd、net_revenue_usd、refund_rate、repeat_rate、rank。

大概口径：不要算测试客户、内部客户和 gift card；有效订单应该是 PAID/SHIPPED/COMPLETED，而且要有 captured payment；退款只算 succeeded；金额转 USD，不要写死汇率；时间按每个 market 自己的本地时区。new/repeat 就按客户历史有没有买过来分。帮我把 SQL 写出来，最好简单解释一下。
