# OpenSearch ChatBI V6.1 需求追踪矩阵

## 使用说明

唯一基线是 docs/baseline/OpenSearch_ChatBI_V6.1_Master_Execution_Spec_含_opensearch-agent_架构校准.md，SHA-256 为 3762adc6ca42745151d01894c835f6d80c9dfb84a6e1ce9624e8b026ed85b6c6。

状态含义：

- IMPLEMENTED：外网工程已实现且有自动化证据；
- DOCUMENTED：架构/操作责任已固化；
- INTERNAL-INPUT：实现已存在，但结果必须由内网真实输入或 Owner verdict 才能闭合；
- NOT-CLAIMED：当前主机不能真实执行，明确不虚报。

## 逐章追踪

| 基线章 | 主题 | 实现位置 | 主要验证 | 状态 |
|---|---|---|---|---|
| 0 | 权威性与执行规则 | AGENTS.md；本文件；基线副本 | delivery_hygiene；基线 hash | IMPLEMENTED |
| 1 | 最终产品定位 | README；frontend/src；presentation | dynamic_dashboard；Dashboard Vitest/E2E | IMPLEMENTED |
| 2 | SQLBot 借鉴边界 | docs/adr；query/analytics 分层 | reference_guardrails | DOCUMENTED |
| 2A | opensearch-agent 校准 | gateway/mcp.py；config/gateway.mcp.yaml；docker/mcp | mcp_adapter；capability_probe；config tests | IMPLEMENTED |
| 3 | 总体架构 | bootstrap.py；orchestration/graph.py；contracts | architecture tests；phase2/3 graph | IMPLEMENTED |
| 4 | Schema Control Plane | semantic/sources、compiler、mapping、package、fts_index | semantic compile/conflict/source/mapping tests | IMPLEMENTED |
| 5 | 指标与分析方法 | registries；analytics/metric_engine、features、rollup | metric_registry；metric_qa；dynamic_rollup | IMPLEMENTED |
| 6 | Data Analyst Planner | agents/analyst_planner.py；orchestration/nodes.py | analyst_planner；planner_validation；G01–G25 | IMPLEMENTED |
| 7 | AnalysisPlan→QueryPlan→DSL | agents/logical_query_planner.py；query/* | plan_compile；phase3_graph；reference_guardrails | IMPLEMENTED |
| 8 | Gateway 与 MCP | gateway/*；config/*.mcp.yaml | mock、mcp_adapter、probe/smoke unit tests | IMPLEMENTED |
| 9 | Result/Dataset/Metric/Statistic | analytics/*；contracts/dataset.py | normalizer、pipeline、metric_qa、composite | IMPLEMENTED |
| 10 | 查询后分析与动态可视化 | agents/insight_dashboard.py；presentation/dashboard.py | insight_dashboard；dynamic_dashboard；chart_preferences | IMPLEMENTED |
| 11 | 回答、Grounding、Evidence | presentation/grounding.py、evidence.py | grounding_dashboard；evidence；workspace API | IMPLEMENTED |
| 12 | Session、多轮、前端 | persistence；orchestration/context；frontend/src | context、recovery、workspace API、Playwright | IMPLEMENTED |
| 13 | API 契约 | api；contracts；OpenAPI/generated.ts | schema_contracts；generate_frontend_types --check | IMPLEMENTED |
| 14 | 工程结构 | 仓库目录；ADR；README | reference_guardrails；CI | IMPLEMENTED |
| 15 | 外网完整/内网轻接入 | scripts；semantic-input/internal-template；本手册 | internal_input_scripts；cutover | IMPLEMENTED + INTERNAL-INPUT |
| 16 | 7 月 Channel Golden | evals/golden；fixtures | G02 等 Golden matrix | IMPLEMENTED |
| 17 | 5–7 月多维 Golden | evals/golden；fixtures | G05 等；dynamic_dashboard | IMPLEMENTED |
| 18 | 测试与评估 | backend/tests；frontend/tests/e2e；CI | 265 backend + 17 frontend + 1 E2E | IMPLEMENTED |
| 19 | 分阶段计划 | docs/gates/phase0–7；project_memory | 各阶段 Gate | DOCUMENTED |
| 20 | 旧工程迁移策略 | 独立 greenfield 目录；ADR | reference_guardrails | IMPLEMENTED |
| 21 | 上线前 Checklist | docs/internal_checklist.md | 手工签字 + probes/shadow | IMPLEMENTED + INTERNAL-INPUT |
| 22 | Definition of Done | verify scripts；test_report | 全量门禁 | IMPLEMENTED，真实项待内网 |
| 23 | 最终执行建议 | README；INTERNAL_AI_START_HERE | 交接审计 | DOCUMENTED |
| 24 | 外网 Codex 协议 | AGENTS.md；delivery hygiene | no TODO/credential scans | IMPLEMENTED |
| 25 | 技术选型/部署 | pyproject/lockfiles；package.json；Compose | deployment_profiles；CI | IMPLEMENTED；Docker run NOT-CLAIMED |
| 26 | 逐文件职责 | 模块目录；ADR；本手册 | architecture import guardrails | IMPLEMENTED |
| 27 | StateGraph 节点/状态所有权 | orchestration/graph.py、state.py、phase nodes | phase2_graph；phase3_graph；Golden | IMPLEMENTED |
| 28 | Contract 目录/版本兼容 | contracts；docs/schemas；OpenAPI | 40 schema snapshots；51 API schemas | IMPLEMENTED |
| 29 | Semantic Compiler | semantic/*；scripts/prepare/compile/configure | compile package/conflicts/internal scripts | IMPLEMENTED |
| 30 | 三 Agent Prompt 协议 | agents/prompts；agents/*.py；llm/client.py | reference_guardrails；cutover；adapter tests | IMPLEMENTED |
| 31 | Query AST/Compiler/Validator | contracts/query.py；query/* | plan_compile；index_router；security Golden | IMPLEMENTED |
| 32 | Gateway/MCP/连接配置 | gateway/*；docker/mcp；config | mcp adapter/probe/config tests | IMPLEMENTED + INTERNAL-INPUT |
| 33 | Normalization/Derived/Metric/QA | analytics/* | pipeline/composite/rollup/metric tests | IMPLEMENTED |
| 34 | Dashboard/ECharts/Grounding/Evidence | presentation/*；SafeChart/EvidenceDrawer | backend presentation + frontend safety/E2E | IMPLEMENTED |
| 35 | Session/API/并发/幂等/前端 | persistence/*；orchestrator.py；api；frontend | repositories/recovery/API/G23–G25/E2E | IMPLEMENTED |
| 36 | 错误/可观测/安全/审计 | observability/audit.py；security；progress | audit、identity、delivery hygiene、security frontend | IMPLEMENTED |
| 37 | 配置/环境变量/启动 | settings.py；.env.example；Compose；scripts/dev | deployment_profiles；network_startup；health | IMPLEMENTED |
| 38 | Mock/Golden/测试矩阵 | rule_based.py；fixtures；evals；tests | G01–G25；full suite | IMPLEMENTED |
| 39 | 分阶段 Gate/交付 | docs/gates；scripts/verify-package | CI 与本地门禁 | IMPLEMENTED |
| 40 | 内网轻量接入 | INTERNAL_AI_START_HERE；integration guides；scripts | cutover/probe/input/shadow tests | IMPLEMENTED + INTERNAL-INPUT |
| 41 | 完整需求追踪 | 本文件 | 人工审阅 + CI references | IMPLEMENTED |
| 42 | 加强 DoD | test_report；final audit；delivery manifest | 全门禁；真实项明确停止条件 | IMPLEMENTED，真实项待内网 |
| 43 | 总任务提示词 | AGENTS.md；本手册 | 内网 AI 强制约束 | DOCUMENTED |
| 44 | 最终架构结论 | README；ADR；project_memory | architecture/cutover guardrails | IMPLEMENTED |

## 关键横向需求追踪

| 需求 | 生产责任边界 | 代码/配置 | 自动化证据 |
|---|---|---|---|
| 只有三个有界 LLM Node | StructuredLLMClient；无 Tool | agents/*；llm/client.py | test_reference_guardrails；cutover |
| Mock 不污染生产 | composition root 仅按 profile 选择 | bootstrap.py；settings.py；llm/cutover.py | identity_settings；cutover 12 项 |
| Agent A 是意图权威 | 真实模型输出 AnalysisPlanDraft | analyst_planner.py；prompt | analyst_planner；planner_validation；Golden |
| Agent B 不输出 DSL | 只输出 QueryPlanDraft | logical_query_planner.py | plan_compile；compiler_owns_dsl |
| Agent C 不计算数字 | 只输出 selector 和 candidate | insight_dashboard.py；grounding.py | insight_dashboard；grounding_dashboard |
| 动态指标 | required/recommended 受治理指标交集 | dashboard.py；metric registry | dynamic_dashboard；metric_qa |
| 动态图表 0/1/N | Agent C + Registry + Dataset | visualization registry；dashboard.py | dynamic_dashboard；chart_preferences |
| 显式图表偏好 | Agent A 结构化；Validator 降级 | AnalysisPlan；phase5；SafeChart | line/heatmap/table tests |
| 不固定二维模板 | tasks/dimensions/grain 驱动 | rule-independent formal chain | error-dimension、overview、table、Pareto Golden |
| 高基数安全 | 无虚假前端 Top-N transform | dashboard.py | high-cardinality downgrade test |
| 复用正确 | 数据签名不变才零查询 | context.py；nodes.py | presentation/explanation + signature-change tests |
| 总分析完整 | required task → claim/limitation | insight prompt；phase5_nodes.py | Agent C repair/coverage tests |
| Evidence 可检查 | 表/公式/QA/授权 DSL | evidence.py；EvidenceDrawer | evidence backend/frontend/E2E |
| 主页面无技术明细 | 业务块过滤 | Dashboard.tsx | Dashboard Vitest |
| SSE 实时且最终收起 | 实际节点事件；前端临时态 | progress.py；stream API/client | stream backend/frontend；E2E |
| 完整执行 QA | 所有 composite 页记录 | phase4_nodes.py；pipeline.py | later-page shard failure test |
| 总轮次超时 | asyncio timeout + retryable FAILED | orchestrator.py；settings | timeout/idempotency test |
| 幂等/恢复/取消 | repository + lock/checkpoint | persistence；orchestrator | repository/recovery/G23/G25 |
| owner scope | 每次读取带 subject | security/repositories/API | G24；workspace API |
| 只读 MCP | required/forbidden binding | gateway/config/docker | mcp adapter/probe/config |
| Schema/OpenAPI 单源 | Pydantic → snapshots/types | contracts；generation scripts | 40/51 drift checks |

## 尚不能由外网闭合的事实

以下不是代码 TODO：

- 真实 Excel/CSV 字段说明和 Mapping；
- 获准 LLM/MCP endpoint、Secret、证书和网络；
- failure/status/分子分母/时区/敏感等级等 Owner 确认；
- 真实索引上的只读 smoke 与 Shadow；
- 真实 Agent A/B/C 的业务质量 verdict；
- 生产身份头、Ingress/SSE 和 Docker 环境验证；
- 业务/数据/安全/运维 Owner 的最终上线签字。

对应流程、Adapter、脚本、门禁和停止条件均已在 INTERNAL_AI_START_HERE.md 中交付。
