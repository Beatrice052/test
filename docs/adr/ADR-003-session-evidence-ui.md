# ADR-003：Session、Evidence 与安全 UI

- 状态：Accepted
- 日期：2026-08-01

## 决策

- SQLite/Alembic Repository 对 Session、Turn、Answer、Dataset、Evidence、idempotency 和 lock 执行 subject-scoped 查询；不存在非所有权读取旁路。
- 完成的 AnswerSnapshot 是不可变恢复单元；刷新、切换和 presentation-only 追问从已持久化对象恢复，不重新查询 OpenSearch。
- Business Evidence 不含 DSL；Advanced Evidence 需要角色；Debug 默认关闭。
- 前端使用 TanStack Query 管 server state、Zustand 管局部 UI state；业务数字只显示后端 Dataset/Metric。
- `SafeChart` 从声明式 ChartSpec 生成固定 ECharts option；不接收 raw option、HTML、formatter function、custom series 或任意 JavaScript。

## 后果

同 `client_turn_id` 重放和 presentation-only 追问不增加 Gateway call；跨 subject 的 Session/Dataset/Evidence 读取返回不可枚举的 not-found。历史页面可在无 Gateway 的情况下完整恢复。
