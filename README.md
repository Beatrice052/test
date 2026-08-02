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

验包使用 lockfile，执行 ruff/format/mypy、全部 backend 与 G01–G25、40 个 Schema snapshot、51 个 OpenAPI 类型、Mock Semantic compile、frontend type/lint/unit/build、Playwright G02/G15/G25，并实际启动/probe Mock readiness 与 UI。

Dashboard 不是固定的 `Channel × Status × Month` 模板。Agent A 根据当前问题和 Semantic Package 中字段的语义角色、能力、别名、成熟度与受治理值动态选择指标、时间和分类维度；确定性 Analytics 再按实际选中的维度派生 rollup、排名、趋势和构成数据，Agent C 只基于已验证数据提出可行图表。前端统一呈现去重后的总分析、KPI、图表解读、边界与追问建议；OpenSearch 聚合结果表、指标计算、质量对账和高级 DSL 统一收纳在证据抽屉。

核心 KPI 只来自本轮 AnalysisPlan 中 `required/recommended` 的受治理 MetricDefinition，不会自动追加类别基数或技术口径检查。总分析按 Agent C 的输出顺序纳入全部去重且已 Grounding 的 Claim；当前 `rule_based` 仅用于无凭证结构回归，分析深度不是正式 LLM 的质量上限。真实模型必须逐项覆盖 required task，并通过 [真实 LLM 切换与 Mock 规则隔离手册](docs/integration/real_llm_cutover_runbook.md) 中的分析完整性验收。

用户发送问题后，前端通过 SSE 展示由实际 LangGraph 节点驱动的进度：Agent A 意图识别、Agent B QueryPlan、确定性 DSL 编译、OpenSearch 检索、Analytics/QA、Agent C 与 Dashboard。最终不可变答案加载后进度自动收起。展示的是可审计阶段和已确认的结构化摘要，不暴露模型私有推理、prompt 或原始 DSL。

用户在初次问题或后续修改中明确指定柱状图、折线图、堆叠柱状图、热力图、环形图、点图、Pareto 或表格时，由 Agent A 将要求写入结构化 `presentation_preference`；Agent C 再根据真实结果选择候选图，Visualization Registry 与 Dataset grain 负责兼容性校验。兼容时优先采用；不兼容时降级为可核查表格并解释原因。图表数量没有固定默认值，允许 0、1 或多张，但每张必须回答不同问题。渲染器目录是可扩展的安全白名单，不允许 LLM 注入任意 ECharts option 或 JavaScript。

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
4. `snapshot-mapping`；
5. `prepare-internal-input` + `compile-internal-semantic`；
6. 业务确认后才运行 `configure-failure-rate`；
7. 固定只读 `smoke-mcp`；
8. `build-shadow-report` 保存六层产物 hash 并完成业务 verdict。

详细文档：

- [内网 AI 从这里开始](docs/integration/INTERNAL_AI_START_HERE.md)
- [需求追踪矩阵](docs/requirements_traceability.md)
- [最终端到端审计](docs/audits/final_end_to_end_audit.md)
- [交付清单](DELIVERY_MANIFEST.md)
- [MCP Adapter](docs/integration/mcp_adapter_guide.md)
- [LLM Adapter](docs/integration/llm_adapter_guide.md)
- [真实 LLM 切换与 Mock 规则隔离](docs/integration/real_llm_cutover_runbook.md)
- [流式分析进度设计](docs/integration/streaming_progress_design.md)
- [LLM 决策边界深度审计](docs/audits/llm_decision_boundary_audit.md)
- [Semantic / Schema](docs/integration/semantic_schema_guide.md)
- [内网上线 Checklist](docs/internal_checklist.md)
- [测试报告](docs/test_report.md)
- [ADR 汇总](docs/adr_summary.md)
- [阶段 Gate](docs/gates/phase7_gate_report.md)

## 安全与凭证

- `.env`、真实 Mapping/Excel、真实数据和报告默认不提交；
- `mock`/`local-os` 使用开发用 Mock Identity；`mcp` 默认使用 `trusted_headers`，生产环境会拒绝 Mock Identity；
- Business Evidence 不含 DSL，Advanced Evidence 需要角色，Debug 默认关闭；
- CSV 防公式注入，所有对象读取 subject-scoped；
- MCP config 只保存 env/Secret reference；Generic API、PPL、Memory 和写 Tool 不绑定；
- `direct` Gateway 不是当前可用旁路，未来启用必须单独 ADR 和全量回归。
