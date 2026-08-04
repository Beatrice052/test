# OpenSearch ChatBI V6.1 内网 AI 执行约束

本仓库的唯一权威需求基线是：

- `docs/baseline/OpenSearch_ChatBI_V6.1_Master_Execution_Spec_含_opensearch-agent_架构校准.md`
- SHA-256：`3762adc6ca42745151d01894c835f6d80c9dfb84a6e1ce9624e8b026ed85b6c6`

任何历史项目、旧提示词、口头约定或既有 RuleBased 逻辑与该基线冲突时，以该文件为准。开始工作前必须完整阅读：

1. `docs/integration/INTERNAL_AI_START_HERE.md`
2. `docs/integration/decision_authority_matrix.md`
3. `docs/requirements_traceability.md`
4. `docs/integration/real_llm_cutover_runbook.md`
5. `docs/integration/multi_agent_orchestration.md`
6. `docs/integration/visualization_agent_architecture.md`
7. `docs/internal_checklist.md`

## 不可破坏的架构边界

- 保持一个模块化 FastAPI 应用、一个 low-level LangGraph StateGraph、三个有界结构化 LLM Node。
- Agent A 负责多轮关系、意图、AnalysisPlan、指标选择、任务与展示偏好；Agent B 只负责逻辑 QueryPlan；Agent C 是同一个有界 Node 内的两个结构化 Pass：先提出 VisualizationCandidate 探索请求，受控 Adapter 返回 Preview 后，再同时生成 ClaimDraft 与 VisualInsightDraft。
- LLM 不得直接访问 MCP、OpenSearch、数据库或任意 Tool；不得生成/执行 raw DSL、PPL、SQL、Python、JavaScript、Plotly spec、ECharts option；不得计算正式指标。Agent C 只能消费受控 VisualizationPreview，不能自由调用绘图库。
- Agent A 的字段候选必须包含经治理的 description/semantic type/capability/compatibility/cardinality 摘要且不得包含 physical path；Agent B 必须通过 `ResolvedFieldDescriptor` 获得同类语义事实。索引发现、Mapping 和 profile 只能由 Bootstrap/Refresh 确定性节点调用 MCP，不能变成 Agent Tool。
- 最终 DSL、索引路由、指标公式、统计、QA、Grounding、图表可行性、Evidence、权限、持久化全部保持确定性。
- 禁止引入 AgentExecutor、ReAct、Supervisor、自由 Tool Loop、LLM→MCP、通用 chat fallback 或前端指标计算。
- `AnalysisPlan → ResolvedAnalysis → QueryPlan → CompiledQuery → ExecutionRecord → DatasetBundle → Claim/Dashboard/Evidence → AnswerSnapshot` 各层不可合并。

## Mock 隔离红线

`backend/app/llm/rule_based.py`、`mock_chart_preferences.py`、`fixture.py`、`recorded.py` 仅服务无凭证测试。严禁：

- 把其中的关键词、意图、指标、维度、时间、图表或 Claim 规则复制到正式 Agent、编排、Query、Analytics 或 Presentation 路径；
- 真实 LLM 失败后静默切换到 RuleBased/Fixture/Recorded；
- 用新增规则让 Mock 看起来像真实开放式分析模型；
- 在 `mcp/prod/production` 中使用 Mock Identity、Mock Semantic Package/Input 或非 MCP Gateway。
- 在 `mcp/prod/production` 中直接使用 `semantic-input/internal-template`，或把模板 Recipe 当成默认任务清单。

正式路径只依赖 `StructuredLLMClient`。若真实端点的 strict JSON Schema 不兼容，只能修改 Adapter 兼容层或端点配置，不能放宽 Contract 或改成自由文本。

## 允许内网补充的内容

仅限基线明确保留的真实输入与确认：

- 真实字段说明 Excel/CSV；
- 真实 OpenSearch Mapping Snapshot；
- 由现有 `snapshot-field-profile` 流程从真实 MCP 生成的受控 FieldProfileSnapshot；
- 获准的 LLM endpoint/model/Secret/证书；
- 获准的只读 OpenSearch MCP endpoint/Secret/证书；
- failure/status、分子分母、时间字段、时区、枚举、敏感等级等业务口径确认；
- 真实数据 Shadow、Golden 与业务 Owner verdict；
- 可信身份头和 Ingress/SSE 环境配置。

除非外部测试证明本仓库存在缺陷，不得以“内网适配”为名重写核心意图、QueryPlan、DSL、Analytics、Dashboard、Evidence、Session 或安全流程。

## 修改门禁

任何影响 Contract、Agent、Query、Analytics、Dashboard、Evidence、状态或安全的修改，提交前必须至少执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/verify-package.ps1
```

若当前主机不是 Node 22.17.0 或没有 Docker，按 `docs/integration/INTERNAL_AI_START_HERE.md` 的分层命令执行，并在报告中明确记录未执行项；不得把静态检查写成已完成的真实联通测试。

正式接入必须额外通过：

```powershell
./scripts/check-real-llm-cutover.ps1 -Output ./reports/real-llm-cutover.json
./scripts/probe-llm.ps1
./scripts/probe-mcp.ps1
```

还必须完成真实只读 Shadow、指标重算、证据定位、G01–G25 语义层验收及业务 Owner verdict。

## 交付纪律

- 不提交 `.env`、Secret、真实业务数据、真实 Mapping/Excel、生产日志、Shadow 明文、运行数据库或构建缓存。
- 所有新增正式能力必须有 Contract、确定性校验、失败路径、单元/集成/Golden 测试和文档。
- Dashboard 的 KPI 数量、图表数量、图表类型、维度和粒度必须由本轮问题、受治理语义和实际数据共同决定，不得固定为四卡、四图或 Channel×Status×Month。
- 用户显式图表偏好由 Agent A 结构化；Agent C Pass 1 基于数据提出 0/1/N 候选；Registry/Validator/Explorer 产生验证 Preview；Agent C Pass 2 将图与同任务、同 Dataset、同 measure 的 Grounded Claim 同时绑定；不兼容时解释并安全降级为表格。
- 每张最终图必须有 purpose、grounded findings、按最终 encoding 生成的 reading guide 和必要 caveat；不得先画固定候选再按文字相似度配结论。
- 主 Dashboard answer-first；技术聚合明细、指标计算、QA/对账放 Business Evidence；DSL 只在 Advanced Evidence 且经过授权时展示。
- 流式 UI 只展示真实阶段和安全结构化摘要，不展示隐藏推理、Prompt、完整用户文本、原始模型输出、Secret 或未授权 DSL；最终答案出现后自动收起。
