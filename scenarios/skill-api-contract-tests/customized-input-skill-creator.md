/api-contract-test-design-skill-creator

帮我把这个付款接口的测试 case 列一下，尽量全一点，表格就行，不用写代码。

下面是我从文档里拷出来的，顺序可能有点乱：

POST /v1/payments

header 里面有 Authorization: Bearer token
还有 Idempotency-Key，必填，最长 64 个字符

body 大概这样：
sourceAccountId string
destinationAccountId string
amount 100.00
currency HKD
scheduledAt 2026-07-01T10:00:00+08:00
note string

规则：
sourceAccountId 和 destinationAccountId 都要有
两个账号不能一样
amount 最小 0.01，最大 1,000,000.00
amount 最多两位小数
currency 只支持 HKD / CNY / USD
scheduledAt 可以不传；如果传了不能是过去时间，也不能超过未来 30 天
note 可以不传，最长 200
登录用户要有 source account 的权限
同一个 Idempotency-Key 加同一个 body 再发一次，要返回原来的 payment 结果
同一个 Idempotency-Key 但是 body 不一样，返回 409
余额不足返回 422
新的成功请求返回 201

response 差不多是：
paymentId string
status PENDING
createdAt timestamp
