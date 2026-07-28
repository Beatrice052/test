# Mock Data Dictionary

## 数据范围

| Index | 文档数 | 时间 |
|---|---:|---|
| `tbl_os_sub_message_2026_06` | 180 | 2026-06 完整月 |
| `tbl_os_sub_message_2026_07` | 186 | 2026-07 完整月 |
| `tbl_os_sub_message_2026_08` | 186 | 2026-08 完整月 |
| 合计 | 552 | 三个月 |

每天每个 Channel 生成两条 document。数据包含 retry、大小写/空格状态变体、
空状态、未知状态、blocked 假值和 review-required 对象。

## 主要 synthetic 字段

| 字段 | Mapping | 用途 | 状态 |
|---|---|---|---|
| `createdTime` | date | 默认业务时间 | synthetic allowed |
| `status` | keyword | `failure_rate.v1` 生命周期状态 | synthetic allowed |
| `statusCode` | keyword | 运营商原始回执码 | synthetic allowed，业务解释未确认 |
| `Status` | keyword | 大小写近似字段歧义测试 | synthetic allowed |
| `pushStatus` | keyword | push 状态候选 | synthetic allowed |
| `letterStatus` | keyword | letter 状态候选 | synthetic allowed |
| `ackFlag` | keyword | ack 标识 | synthetic allowed |
| `channel` | keyword | SMS/Email/WhatsApp | synthetic allowed |
| `route` | keyword | ROUTE_A/B/C | synthetic allowed |
| `providerName` | keyword | synthetic provider | synthetic allowed |
| `retryCount` | integer | retry 测试 | synthetic allowed |
| `latencyMs` | long | 数值字段测试 | synthetic allowed |
| `deliveryMeta` | object | Mapping-only 子字段测试 | review_required |

## Mock blocked 字段

```text
messageBody
customerName
phoneNumber
emailAddress
bankAccount
customerId
```

这些字段只用于验证后端阻断，值均为假数据。它们不得进入候选、DSL、结果、
图表、总结或 Evidence。

## 状态分布

合成器轮换：

```text
SENT
INPROGRESS
FAILED
ACKFAIL
QUEUED
null
```

部分非空值会转为小写或加入首尾空格，以验证 normalize(trim, upper)。

## 可重复生成

```powershell
python scripts/generate_mock_data.py
```

生成器是确定性的，同一版本应产生相同文档数量和指标结果。
