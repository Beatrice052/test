# Phase 3 Gate Report — Agent B、Query 与 Gateway

- 日期：2026-08-01
- 结果：**PASSED**
- 唯一基线 SHA-256：`3762adc6ca42745151d01894c835f6d80c9dfb84a6e1ce9624e8b026ed85b6c6`
- Semantic Package：`sp_c882cd989899b08f`

## 1. 本阶段交付

- `LogicalQueryPlannerAgent` 只读取已确认的 `AnalysisPlan` 与 `ResolvedAnalysis` ID，不读取 Mapping、物理字段、DSL、Gateway 或 MCP Tool。
- `QueryPlanFinalizer` 强制 AnalysisPlan 身份、候选 ID、时间范围、必选过滤器、指标版本、路由、预算、依赖拓扑和最多一轮依赖查询。
- `IndexRouter` 按 `Asia/Hong_Kong` 的半开区间 `[from,to)` 枚举月索引，并应用 policy、可用索引及逐月字段兼容性。
- 关闭的 Query AST 与 `DslCompiler` 只产生只读聚合 DSL；terms/composite 由估算桶数确定，composite 翻页保持 base fingerprint。
- `CompiledQueryValidator` 再核对路由、字段、时间、计划身份和 DSL 白名单，拒绝脚本、运行时字段、写操作及未解析物理字段。
- `DependentQueryBinder` 从真实 q1 `RawSearchResult` 的 bucket 中抽取 Top N 值，再绑定并编译 q2；Agent B 不接触结果值。
- `MockOpenSearchGateway` 按 query fingerprint 注册结果/故障并记录调用次数；`GatewayExecutor` 只重试可重试 Gateway 错误。
- `McpOpenSearchGateway`、官方 MCP transport、配置化工具绑定与一次性 capability probe 已实现；适配 object/string `query_dsl`、JSON content block、CSV 与返回大小限制。
- Phase 3 StateGraph 包含 Agent B、最多两次定向修复、finalize、compile、validate 及结构化失败终态。

## 2. 核心边界

1. 公共 API 没有 raw DSL 字段；编译器入口只接受已终结 `QueryPlan` 和 `step_id`。
2. Agent 无 Gateway/MCP/数据库 import，Structured LLM 接口无 tool 参数。
3. `GenericOpenSearchApiTool` 与 `PPLQueryTool` 只存在于禁止清单，未绑定到任何允许能力。
4. 所有 OpenSearch 返回先在 Gateway Adapter 内规范为 `RawSearchResult`，业务层不解析 MCP content block 或 CSV。
5. Agent B 两次修复仍无效时返回 `PLAN_QUERY_PLAN_INVALID`，不执行猜测出的索引、字段或 DSL。

## 3. 实际验证结果

| 检查 | 结果 |
|---|---:|
| Backend pytest | 135 passed / 0 failed / 0 skipped |
| Phase 3 专项（architecture/query/gateway/graph） | 21 passed |
| ruff check | passed |
| ruff format check | passed（121 files） |
| mypy | passed（95 source files） |
| 权威 Schema Snapshot | 39 matched / 0 diff |
| Mock semantic compile | PASSED / `sp_c882cd989899b08f` |

专项证据包括：

- 2026 年 5–7 月精确路由至 05、06、07 三个月，未误包含 04；按 HK 时区保持半开边界。
- 映射不兼容月份单独标为 incompatible，兼容月份仍可按策略回答。
- 小规模维度使用 terms，大规模维度使用 composite，`after_key` 只改变页内容 hash，不改变 base query fingerprint。
- 两阶段 Top N 实际调用 Mock Gateway 获取 q1 bucket，提取 `SMS`、`EMAIL`，绑定进 q2 DSL 后再执行 q2；共两次 Gateway 调用。
- 第二层依赖查询被预算策略拒绝。
- timeout 可重试并在第二次成功；protocol error 不重试；执行记录保留 attempt、错误码、timed_out 与结果 hash。
- 注入 script 或未解析物理字段均被 validator 拒绝。
- Agent B 非法数据集经过恰好两次修复后进入结构化失败终态。

## 4. Gate 判定

| Phase 3 Gate | 证据 | 判定 |
|---|---|---:|
| raw DSL 无入口 | OpenAPI architecture test + closed compiler signature | PASS |
| 5–7 月索引与时间正确 | IndexRouter unit tests | PASS |
| Generic API/PPL 未绑定 | Python AST + MCP YAML binding tests | PASS |
| 两阶段 Top N 使用真实 q1 参数 | q1 Gateway result → binder → q2 DSL/Gateway integration test | PASS |
| Gateway fault tests | retryable timeout / terminal protocol / fixture missing tests | PASS |

**Phase 3 Gate：PASSED。**

## 5. 下一阶段

进入 Phase 4：Raw Result Parser、递归 Bucket Normalizer、DatasetBundle、稳定 row_id、Derivation、Metric Formula、Statistic、QA/Reconciliation 和 Feature Summary。真实凭证、真实语义输入与业务口径确认仍是唯一保留给内网的输入，核心实现不外包给内网。
