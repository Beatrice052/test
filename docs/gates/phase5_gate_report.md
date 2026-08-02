# Phase 5 Gate Report — Agent C、Dashboard 与 Evidence

- 日期：2026-08-01
- 结果：**PASSED**
- 唯一基线 SHA-256：`3762adc6ca42745151d01894c835f6d80c9dfb84a6e1ce9624e8b026ed85b6c6`
- Semantic Package：`sp_c882cd989899b08f`

## 1. 本阶段交付

- `InsightDashboardAgent` 只接收 AnalysisPlan、Dataset schema、bounded FeatureSummary、Metric Definition View、DataQA、Visualization Intent 与 Dashboard budget；不接收完整 Dataset rows、RawResult、CompiledQuery、DSL、Mapping、MCP 或 Tool。
- Agent C 只输出 `ClaimDraft` selector 和 `VisualizationCandidate` intent，不计算数字、不构造 row_id、不输出 ECharts option/JavaScript/HTML。
- `ClaimGrounder` 支持 `first`、`argmax`、`argmin`、`where` 的受控 selector；强制 Dataset/column 存在、selector 唯一、ranking 全体比较、比例 numerator/denominator、无 ERROR/FATAL QA、无因果升级。
- Grounding 失败的 Claim 直接删除并记录 `GroundingFailure`，不会“尽量保留”；每个落地 `ClaimSpec` 至少有一个精确到 dataset/row/column/metric 的 EvidenceRef。
- `ChartFeasibilityValidator` 实现 ACCEPT、ACCEPT_WITH_TRANSFORM、DOWNGRADE_TO_TABLE、REJECT；仅允许 sort、Top N + Others、stable color assignment 等受控 transform。
- `DashboardBuilder` 执行可行性、低价值删除、去重、布局和预算；支持多图复用一个 Dataset、空结果、warning 与 data table fallback。
- `DashboardSpec` 只有安全声明字段；契约中不存在 raw option、formatter function、custom series、renderItem、graphic、JavaScript 或 HTML。
- `EvidenceBuilder` 从同一 AnswerSnapshot 对象构建 Business/Advanced 层；Business 不含 DSL，Advanced 保存 QueryPlan、CompiledQuery、Execution 和 Result Contract 快照；凭证、endpoint、prompt、raw documents 被列入 redaction。
- `EvidenceExporter` 生成稳定 CSV，规范化嵌套 metadata，并防止 `= + - @` 公式注入；Evidence layer 由角色策略控制。
- Phase 5 已接入同一 StateGraph 并原子持久化完整 AnswerSnapshot、active analytical context、Turn 与 idempotency 状态。
- Agent C adapter 失败时使用确定性 Claim/table fallback，仍生成 Evidence，AnswerStatus=`PARTIAL`。

### 动态分析与 Dashboard 校准（2026-08-01）

- `Channel × Status × Month` 仅是 Mock 语义包在“最近三个月消息情况”问题下的一次解析结果，不是代码模板。
- Agent A 从检索到的字段候选中依据 `semantic_type`、能力、别名、成熟度、受治理值和问题相关性选择指标、时间维度、分类维度与过滤值；后续逻辑计划只引用这些实际选择。
- Analytics 对实际 `group_by` 做通用 additive rollup 与 reconciliation，可派生整体、单维、时间×分类及经业务确认的构成视图；字段名不要求以 Channel、Status 或 Month 结尾。
- Agent C 根据 AnalysisPlan、Dataset schema、FeatureSummary、完整性和变化度提出 Grounded Claim 与图表候选；Dashboard Builder 再决定趋势、分期对比、排名、构成或业务表格降级，并生成完整总分析、本轮计划选择的 KPI、图表解读、边界和追问建议。技术聚合明细、指标口径和完整 QA 不进入主 Dashboard。
- 回归包含另一类“按错误码分析”问题：系统选择时间＋错误码维度且不选择 Channel，证明分析粒度与图表没有写死。
- 图表可行性新增两条硬不变量：encoding 必须覆盖 Dataset 的完整 grain；每个 encoding key 必须唯一。前端 SafeChart 再执行同样的防御性校验，不再静默覆盖重复类别。
- 用户明确指定图型时，统一解析器在初次提问和后续展示变更中复用；兼容性由 Visualization Registry、分析关系和实际 encoding 决定。热力图使用真实二维 renderer，不再只是修改类型标签。

## 2. Gate 证据

- Agent C payload 测试确认 dataset schema 无 `rows`，整个 payload 无 query_dsl、raw_results、compiled_queries、MCP 或 tool binding。
- ranking 与 ratio Claim 分别解析到唯一 SMS 行；比例显示 `22.22%` 并保留 20/90 的 metadata evidence。
- causal、ambiguous、QA blocked Claim 被删除；Grounded Claim 的 EvidenceRef 覆盖率为 100%。
- 两个不同 intent 的图共同引用 `channel_metrics`，Bundle 中仍只有一个 Dataset；相同候选去重；常数度量图被动态删除并降为数据表。
- Rule-based Agent C 故障注入后，端到端图仍返回持久化的 PARTIAL Answer、grounded fallback Claim、data table 与 Evidence。
- 完成后的同 `client_turn_id` 重放返回原 AnswerSnapshot，Gateway 调用数不增加。
- Business Evidence 序列化不含 query_dsl；Advanced Evidence 包含原快照 query_dsl；历史对象不重新查询。

## 3. 实际验证结果

| 检查 | 结果 |
|---|---:|
| Backend pytest | 162 passed / 0 failed / 0 skipped |
| Phase 5 architecture/Agent C/presentation/graph 专项 | 20 passed |
| ruff check | passed |
| ruff format check | passed（152 files） |
| mypy | passed（116 source files） |
| 权威 Schema Snapshot | 39 matched / 0 diff |
| Mock semantic compile | PASSED / `sp_c882cd989899b08f` |

## 4. Gate 判定

| Phase 5 Gate | 证据 | 判定 |
|---|---|---:|
| Claim Grounding 100% | 每个保留 Claim 均有 EvidenceRef；失败 Claim 删除 | PASS |
| 没有 raw ECharts option | Dashboard Schema recursive property guard | PASS |
| 多图复用 Dataset | rank + composition 共用 `channel_metrics` | PASS |
| 低价值图动态删除 | 常数度量无 chart，保留 validated table | PASS |
| Debug 与 Business Evidence 分层 | Business/Advanced 内容与角色访问测试 | PASS |

**Phase 5 Gate：PASSED。**

## 5. 下一阶段

进入 Phase 6：完整 Session/Turn/Answer/Dataset/Evidence/Semantic API、OpenAPI 前端类型、React Session Workspace、Timeline、Dashboard Grid、ECharts safe adapter、Evidence Drawer、CSV，以及 loading/error/cancel/restore。
