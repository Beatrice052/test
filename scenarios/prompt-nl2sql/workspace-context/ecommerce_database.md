# Existing Workspace Database Context: Ecommerce Analytics

This file simulates a database context that already exists in the user's VS Code workspace. It is local reference material for both A and C groups. Runtime user input should not paste this entire file into Copilot Chat.

## Business Background

The company runs ecommerce businesses in several markets. Each market has its own business timezone, and reporting is based on market-local month.

Orders, order items, payments and refunds are stored separately. They have one-to-many relationships, so SQL must not simply join all fact tables and aggregate at the end.

Amounts are stored in order currency. USD reporting must use `daily_fx_rate`; do not hard-code exchange rates.

## Tables

### `dim_market`

Market dimension.

| Column | Meaning |
|---|---|
| `market_code` | Market code, primary key, such as `TW`, `HK`, `SG` |
| `market_name` | Market display name |
| `business_timezone` | Business timezone, such as `Asia/Taipei`, `Asia/Hong_Kong`, `Asia/Singapore` |

### `dim_customer`

Customer dimension.

| Column | Meaning |
|---|---|
| `customer_id` | Customer ID, primary key |
| `market_code` | Customer market, references `dim_market.market_code` |
| `created_at` | Customer creation timestamp, `timestamptz` |
| `customer_type` | Customer type: `NORMAL`, `VIP`, `INTERNAL` |
| `is_test_customer` | Whether this is a test customer |

### `dim_product`

Product dimension.

| Column | Meaning |
|---|---|
| `product_id` | Product ID, primary key |
| `category` | Product category |
| `is_gift_card` | Whether this product is a gift card |

### `fact_order`

Order header fact table.

| Column | Meaning |
|---|---|
| `order_id` | Order ID, primary key |
| `customer_id` | Ordering customer, references `dim_customer.customer_id` |
| `market_code` | Order market, references `dim_market.market_code` |
| `order_status` | Order status: `CREATED`, `PAID`, `SHIPPED`, `COMPLETED`, `CANCELLED`, `FAILED` |
| `ordered_at` | Order timestamp, `timestamptz` |
| `currency` | Order currency, such as `TWD`, `HKD`, `SGD`, `USD` |

### `fact_order_item`

Order line item fact table.

| Column | Meaning |
|---|---|
| `order_item_id` | Order item ID, primary key |
| `order_id` | Parent order, references `fact_order.order_id` |
| `product_id` | Product, references `dim_product.product_id` |
| `quantity` | Quantity |
| `item_gross_amount` | Line gross amount in order currency |
| `item_discount_amount` | Line discount amount in order currency, nullable |

### `fact_payment`

Payment fact table. One order may have multiple payment records.

| Column | Meaning |
|---|---|
| `payment_id` | Payment ID, primary key |
| `order_id` | Parent order, references `fact_order.order_id` |
| `payment_status` | Payment status: `AUTHORIZED`, `CAPTURED`, `FAILED`, `REFUNDED` |
| `captured_at` | Capture success timestamp, `timestamptz`, nullable |
| `captured_amount` | Captured amount in order currency |

### `fact_refund`

Refund fact table. One order may have multiple refund records.

| Column | Meaning |
|---|---|
| `refund_id` | Refund ID, primary key |
| `order_id` | Parent order, references `fact_order.order_id` |
| `refund_status` | Refund status: `REQUESTED`, `SUCCEEDED`, `FAILED` |
| `refunded_at` | Successful refund timestamp, `timestamptz` |
| `refund_amount` | Refund amount in order currency |

### `daily_fx_rate`

Daily foreign exchange table.

| Column | Meaning |
|---|---|
| `rate_date` | Local date used for FX matching |
| `currency` | Currency |
| `usd_rate` | USD conversion rate for 1 unit of currency |

## Business Rules

1. Valid order statuses are `PAID`, `SHIPPED` and `COMPLETED`.
2. A valid revenue order must also have at least one `fact_payment.payment_status = 'CAPTURED'` record.
3. `CREATED`, `CANCELLED` and `FAILED` orders are excluded from revenue, customer metrics and first-purchase logic.
4. Exclude customers where `dim_customer.is_test_customer = true`.
5. Exclude customers where `dim_customer.customer_type = 'INTERNAL'`.
6. Exclude product lines where `dim_product.is_gift_card = true`.
7. Line revenue is `item_gross_amount - COALESCE(item_discount_amount, 0)`.
8. Gross revenue USD uses the captured payment local date in `dim_market.business_timezone` to join `daily_fx_rate`.
9. Refund revenue USD uses the successful refund local date in `dim_market.business_timezone` to join `daily_fx_rate`.
10. Only `fact_refund.refund_status = 'SUCCEEDED'` refunds count.
11. Refund is order-level. For category reporting, allocate each successful refund to non-gift-card categories by that category's share of non-gift-card line revenue within the order.
12. New paying customers are customers whose first valid non-gift-card order in that market happened in the reporting month and who bought the category in that month.
13. Repeat paying customers are customers who bought the category in the reporting month and had at least one valid non-gift-card order before that month.
14. Paying customers are distinct customers who bought the category in the reporting month.
15. Repeat rate is `repeat_paying_customers / paying_customers`.
16. Refund rate is `refund_amount_usd / gross_revenue_usd`.
17. Top category ranking is per local month and market, ordered by `net_revenue_usd DESC`, then `category ASC`.
