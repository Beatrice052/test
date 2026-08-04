# OpenSearch ChatBI V6.1

Greenfield、Mock-first、Adapter-based 的受治理 OpenSearch ChatBI 完整参考实现。项目严格以 [仓库内权威基线](docs/baseline/OpenSearch_ChatBI_V6.1_Master_Execution_Spec_含_opensearch-agent_架构校准.md)（SHA-256 `3762adc6ca42745151d01894c835f6d80c9dfb84a6e1ce9624e8b026ed85b6c6`）为唯一需求基线。

Phase 0–7 已通过 Gate；Phase 8 的外网脚本、模板和 Checklist 已完成，状态为 `READY_FOR_INTERNAL_SHADOW`。剩余项只有真实 Excel、真实 Mapping、真实 MCP/LLM 配置与 Secret、failure/status 业务确认、真实数据 Shadow 对账，不需要修改核心代码。

## 架构

```text
React Session Workspace
        ↓ typed API
模块化 FastAPI + subject-scoped repositories
        ↓
一个 low-level LangGraph StateGraph
  ├─ DataAnalystPlanner（结构化，不持有 Tool）
  ├─ LogicalQueryPlanner（逻辑计划，不生成最终 DSL）
  └─ InsightDashboardAgent（FeatureSummary，不计算指标/option）
        ↓ deterministic only
Semantic Resolver → Query Finalizer/Compiler/Validator
→ Mock 或官方 MCP Gateway → Result/Metric/Statistic/QA
→ Grounding/Dashboard/Evidence → immutable AnswerSnapshot
```

禁止 AgentExecutor/ReAct/自由 Tool Loop、LLM→MCP、LLM raw DSL/PPL/Python/JavaScript、LLM 正式指标计算、一图一查、前端指标公式和任意 ECharts raw option。

## 环境

- Python 3.12.x（`.python-version`）+ uv
- Node.js 22.17.0（`.node-version` / `.nvmrc`）+ npm
- Docker Compose（仅 Docker profiles 需要）

## Mock 本地启动

Windows PowerShell：

```powershell
./scripts/dev.ps1
```

若系统 Execution Policy 禁止脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/dev.ps1
```

Linux/macOS：

```bash
./scripts/dev.sh
```

- Frontend：`http://127.0.0.1:5173`
- Backend：`http://127.0.0.1:8000`
- Readiness：`http://127.0.0.1:8000/api/v1/health/ready`

Mock 启动不需要 API Key、OpenSearch 凭证、MCP endpoint 或内网连接。

## 一键验包

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/verify-package.ps1
```

```bash
./scripts/verify-package.sh
```

验包使用 lockfile，执行 ruff/format/mypy、全部 backend 与 G01–G25、41 个 Schema snapshot、59 个 OpenAPI 类型、Mock Semantic compile、frontend type/lint/unit/build、Playwright G02/G15/G25，并实际启动/probe Mock readiness 与 UI。

Dashboard 不是固定的 `Channel × Status × Month` 模板。Agent A 只决定本轮业务目标、候选正式/受控派生指标、取数任务和显式展示偏好；Agent B 只决定最小充分的逻辑 QueryPlan。查询与 QA 后，Agent C 才作为数据分析师基于实际 Dataset 特征动态选择要分析的数值列、统计方法和图表候选，并以严格 `AnalyticsToolRequest` / `VisualizationCandidate` Contract 交给宿主执行。宿主只运行版本化的统计方法和安全图表 Adapter；它不代替 Agent C 决定“该分析什么”。C2 在拿到统计结果与已验证 Preview 后形成总洞察、动态 KPI 选择和每图解释。非空且 QA 可用的 ChatBI 回答必须保留 1/N 张诚实图表；若 Agent C 没有给出可行图，会透明标记 PARTIAL，而不会用固定模板伪造一张图。详见 [Agent C 双阶段可视化架构](docs/integration/visualization_agent_architecture.md)。

完整的逐节点“AI 判断 / 程序判断 / 输入 / 输出 / 失败策略 / 验收证据”见 [三 Agent 全流程决策权与验收矩阵](docs/integration/decision_authority_matrix.md)。其中明确：`RuleBasedMockLLMClient` 的关键词和固定示例任务只用于本地回归，正式 Agent A/B/C 必须由真实结构化 LLM 按本轮问题和真实数据动态决策；正式切换门禁会拒绝 Mock、固定任务 bundle 以及直接使用 `internal-template`。

主流程是一个确定性 LangGraph 编排器与三个有界专业 Agent，不是自由 Supervisor/Swarm。Agent A 的候选和 Agent B 的 `ResolvedFieldDescriptor` 都能使用真实 Excel description、字段语义类型、能力、跨月兼容性与可选 cardinality 画像；两者都看不到 physical path 或 raw documents。MCP 的索引发现、Mapping 与 `size:0` 字段画像只在 Bootstrap/Refresh 阶段执行。详见 [受控多 Agent 编排](docs/integration/multi_agent_orchestration.md) 和 [MCP Adapter 指南](docs/integration/mcp_adapter_guide.md)。

已注册 MetricDefinition 是正式业务 KPI/受控派生公式的认证来源，不是 Agent C 的分析上限：LLM 可选择任何已验证 Dataset 中的受治理数值 metric/measure 做探索性统计，但不能发明业务公式或把探索结果冒充正式 KPI。KPI 卡片也不是 Agent A 的默认指标列表，而是 C2 在结果出来后选择的标量值；无高价值标量时可以没有卡片。总分析由 C2 选定且 Grounding 的 `overall_claim_ids` 组成，图表解释只显示必要的“图表解读”，不显示机械的“本图回答/如何阅读/证据提示”文案。`rule_based` 仅用于无凭证结构回归，分析深度不是正式 LLM 的质量上限。

用户发送问题后，前端通过 SSE 展示由实际 LangGraph 节点驱动的进度：Agent A 意图识别、Agent B QueryPlan、确定性 DSL 编译、OpenSearch 检索、Analytics/QA、Agent C 与 Dashboard。最终不可变答案加载后进度自动收起。展示的是可审计阶段和已确认的结构化摘要，不暴露模型私有推理、prompt 或原始 DSL。

用户在初次问题或后续修改中明确指定柱状图、折线图、堆叠柱状图、热力图、环形图、点图、Pareto 或表格时，由 Agent A 将要求写入结构化 `presentation_preference`；Agent C 根据真实结果提出候选，Visualization Explorer 负责验证。兼容时优先采用；不兼容时保留可核查表格并说明原因，同时仍保留另一张真实图表（除非数据为空或 QA 阻断）。图表数与图型没有固定默认值，但每张图必须回答不同问题、包含业务 purpose、Grounded finding 和必要 caveat；前端以简洁“图表解读”展示。当前 renderer 是安全 ECharts Adapter；Plotly 未实现/未启用，新增 renderer 必须走 ADR、Contract、Adapter 和测试，LLM 不能注入绘图代码。

## Docker profiles

```bash
docker compose --profile mock up --build
docker compose --profile local-os up --build
docker compose --profile mcp up --build
```

- `mock`：frontend + backend(rule-based Mock LLM + fixture Gateway)，无 Key；
- `local-os`：frontend + backend + OpenSearch + deterministic fixture loader + 锁定的官方只读 MCP Server；
- `mcp`：frontend + backend，MCP/LLM endpoint 与 Secret 从环境注入；默认要求可信反向代理注入身份头。

三个 profile 默认都暴露 UI `5173`，应一次只启用一个。`local-os` 应用仍走 MCP，不旁路直连 OpenSearch。

## 内网轻接入

内网 AI 必须先读 [完整接入与验收手册](docs/integration/INTERNAL_AI_START_HERE.md)，再按 [Phase 8 手册](docs/integration/internal_handoff.md) 执行：

1. `verify-package` 离线验包；
2. `check-real-llm-cutover`，确认正式配置与 Mock 规则隔离；
3. `probe-mcp` / `probe-llm`；
4. 用已审核 pattern 执行 `snapshot-mapping`，固化 exact indices 与 Mapping；
5. `prepare-internal-input` + staging `compile-internal-semantic`；
6. `snapshot-field-profile` 生成 Policy-safe `size:0` 字段画像，再正式编译；
7. 业务确认后才运行 `configure-failure-rate`；
8. 固定只读 `smoke-mcp`；
9. `build-shadow-report` 保存六层产物 hash 并完成业务 verdict。

详细文档：

- [内网 AI 从这里开始](docs/integration/INTERNAL_AI_START_HERE.md)
- [需求追踪矩阵](docs/requirements_traceability.md)
- [最终端到端审计](docs/audits/final_end_to_end_audit.md)
- [交付清单](DELIVERY_MANIFEST.md)
- [MCP Adapter](docs/integration/mcp_adapter_guide.md)
- [LLM Adapter](docs/integration/llm_adapter_guide.md)
- [真实 LLM 切换与 Mock 规则隔离](docs/integration/real_llm_cutover_runbook.md)
- [受控多 Agent 编排与字段元数据](docs/integration/multi_agent_orchestration.md)
- [流式分析进度设计](docs/integration/streaming_progress_design.md)
- [LLM 决策边界深度审计](docs/audits/llm_decision_boundary_audit.md)
- [Semantic / Schema](docs/integration/semantic_schema_guide.md)
- [内网上线 Checklist](docs/internal_checklist.md)
- [测试报告](docs/test_report.md)
- [ADR 汇总](docs/adr_summary.md)
- [阶段 Gate](docs/gates/phase7_gate_report.md)

## 安全与凭证

- `.env`、真实 Mapping/Profile/Excel、真实数据和报告默认不提交；
- `mock`/`local-os` 使用开发用 Mock Identity；`mcp` 默认使用 `trusted_headers`，生产环境会拒绝 Mock Identity；
- Business Evidence 不含 DSL，Advanced Evidence 需要角色，Debug 默认关闭；
- CSV 防公式注入，所有对象读取 subject-scoped；
- MCP config 只保存 env/Secret reference；Generic API、PPL、Memory 和写 Tool 不绑定；
- `direct` Gateway 不是当前可用旁路，未来启用必须单独 ADR 和全量回归。
