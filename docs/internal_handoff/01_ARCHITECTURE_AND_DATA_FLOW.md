# 架构与数据流

## 权威链路

```text
User / Session
  → Agent A (AnalysisPlan)
  → deterministic Resolver (ResolvedAnalysis)
  → Agent B (logical QueryPlan)
  → Finalizer + AST + Compiler (CompiledQuery)
  → read-only MCP Gateway (RawSearchResult + ExecutionRecord)
  → Parser + Normalizer (base Dataset)
  → Metric Engine + Rollup + QA (derived/calculation Dataset)
  → task-aware FeatureSummary
  → Agent C1 (AnalyticsToolRequest + VisualizationCandidate)
  → Host StatisticEngine + chart feasibility/preview
  → Agent C2 (ClaimDraft + KPI/visual interpretation)
  → ClaimGrounder
  → DashboardSpec + EvidencePackage + immutable AnswerSnapshot
```

## Contract 与 Owner

| Contract | 产生者 | 消费者 | 不变量 |
|---|---|---|---|
| `AnalysisPlan` | Agent A + validator | Resolver、Agent B | 只引用候选 semantic IDs，任务有 required/recommended/optional |
| `ResolvedAnalysis` | Resolver | Agent B、Finalizer | Policy、字段能力、Measure、Entity member 和跨月兼容性已绑定；给 Agent B 的 descriptor 无 physical path |
| `QueryPlan` | Agent B + Finalizer | Compiler | N 维逻辑计划、最小充分 grain、预算、依赖和 task IDs；无 DSL/MCP tool |
| `CompiledQuery` | Compiler | Gateway、Parser | 闭合 AST 生成 `size:0` 只读 DSL；fingerprint 和 query semantics 固定 |
| `ExecutionRecord` | Gateway Executor | QA、Evidence | attempt、timeout、shard、page、bucket、row、raw hash 与 artifact trace |
| `DatasetBundle` | Analytics Host | Agent C、Dashboard、Grounding | typed columns、base/derived tables、完整性、内部 QA 与 reconciliation |
| `FeatureSummary` | Analytics Host | Agent C1/C2 | task、grain、完整性、范围、受控样例和统计结果；ERROR/FATAL 数据不得进入 |
| `AnalyticsToolResult` | GovernedAnalyticsTool | Agent C2、Evidence | 注册方法、确定性参数、result/value paths、calculation table ID |
| `DashboardSpec` | DashboardBuilder | Safe frontend renderer | 声明式图表；无 JavaScript/HTML/raw option |
| `EvidencePackage` | EvidenceBuilder | Evidence API/Drawer | 原始结果、source/calculation tables、技术口径、claim trace、重要限制 |
| `AnswerSnapshot` | Phase 5/persistence | Session restore/API | 不可变、subject-scoped、跨恢复 hash 一致 |

## Mock 与正式路径

Mock profile 由 composition root 注入 `RuleBasedMockLLMClient`、`MockOpenSearchGateway` 和 `compiled-semantic/mock`，数据完全合成。正式 profile 必须注入 `openai_compatible` LLM、approved MCP Gateway、真实 compiled package 与可信身份。Agent、Resolver、Compiler、Analytics、Grounding、Dashboard 和 Evidence 是同一套正式代码；Mock 规则不得复制进这些模块。

## Evidence 数据流

每个成功 query 的合并后 `RawSearchResult` 先写为 JSON artifact；同一份 buckets 由 Parser/Normalizer 生成 base Source Result Table。所有后续 Metric、Rollup 和 Host statistic 分别形成 calculation table 或 statistical artifact。ClaimGrounder 只接受唯一 row selector 或统计 value path，EvidenceBuilder 再把 table ID 解析为实际 artifact ID/hash。

完整 QA 仍保存在 owner-scoped `AnswerSnapshot.dataset_bundle.data_qa`、后台日志和调试路径；Evidence Drawer 只显示总体状态、material warnings、blocked reasons、完整性和 reconciliation 摘要。

## Session、reuse 与 requery

- `client_turn_id` 提供幂等；Session/Turn/Answer/Dataset/Artifact 查询均带 subject ownership。
- presentation-only follow-up 可复用 Dataset，但会重新运行相应 Agent C pass 和验证。
- filter/time/dimension/task/metric/measure/method/grain 或 semantic package 签名变化会强制 requery。
- checkpoint 仅保存安全状态引用；最终 AnswerSnapshot 原子发布。取消、超时和 retryable 状态不会发布半成品答案。
