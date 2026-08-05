# Project Memory — OpenSearch ChatBI V6.1

最后更新：2026-08-04

状态：READY_FOR_INTERNAL_SHADOW

## 唯一权威基线

- 文件：docs/baseline/OpenSearch_ChatBI_V6.1_Master_Execution_Spec_含_opensearch-agent_架构校准.md
- SHA-256：3762adc6ca42745151d01894c835f6d80c9dfb84a6e1ce9624e8b026ed85b6c6
- 旧工程、旧文档和 Mock 规则不得覆盖 V6.1 Contract、架构或 Gate。

## 冻结决策

1. Greenfield、Mock-first、Adapter-based。
2. 一个模块化 FastAPI、一个 low-level LangGraph StateGraph、三个有界结构化 LLM Node。
3. Agent A 决定多轮/意图/AnalysisPlan/指标/任务/展示偏好；Agent B 决定逻辑 QueryPlan；Agent C 先动态选择受治理统计分析和 VisualizationCandidate，再基于实际结果/Preview 决定总体洞察、KPI 与图表解释。
4. Agent 没有自由 Tool/Gateway/DB；C1 只能通过严格 `AnalyticsToolRequest` 请求 Host 执行已注册方法。不生成 DSL、业务公式、ECharts/Plotly/Python raw code。
5. DSL、认证指标公式、统计执行、QA、Grounding、图表可行性、Evidence、持久化均确定性；LLM 决定分析问题、分析对象、统计方法和解释。
6. AnalysisPlan → ResolvedAnalysis → QueryPlan → CompiledQuery → ExecutionRecord → DatasetBundle → AnswerSnapshot 各层不可合并。
7. Semantic Package 由 Excel/CSV + Mapping + Registry + Policy 确定性编译并 hash 版本化。
8. 真实 OpenSearch 默认使用获准的官方只读 MCP；direct 不是当前可用旁路。
9. 正式 LLM 使用 OpenAI-compatible strict JSON Schema；无通用 chat escape hatch。
10. rule_based/fixture/recorded 仅用于测试；正式失败不得静默回退。
11. 正式环境拒绝 Mock Identity、Mock LLM、Mock Semantic Package/Input、直接使用 internal-template 和非 MCP Gateway。
12. 业务时间统一 Asia/Hong_Kong 和 [from,to)。
13. message_record_count 是记录数；未确认前不称“发送量”。
14. failure_rate 必须有确认的状态分组、分子、分母、排除项、最小分母、Owner 和版本。
15. Dashboard answer-first；聚合明细、指标计算、QA 放 Business Evidence；DSL 仅授权 Advanced Evidence。
16. MetricDefinition 只认证正式 KPI/受控派生公式；C2 从实际标量 Dataset 动态选择 KPI，数量可为 0/1/N；C1 可在任何受治理数值列上选择已注册统计方法。
17. 图表由 Agent C + Registry + Dataset 共同决定；非空且 QA 可用时必须为 1/N，空/QA 阻断才可无图；用户偏好兼容则采用，不兼容请求安全降级为表且仍保留诚实可行图。
18. SafeChart 不执行任意 option/HTML/JavaScript。
19. 总分析只使用 C2 显式选定的 `overall_claim_ids`；它不自动拼接所有图表 finding，也不创建重复关键发现页；required task 必须 claim 或 limitation。
20. 多轮复用需要 scope 与每个 task 的 metric/dimension/grain/statistical method 数据签名不变；否则强制 requery。纯换图重跑 Agent C Pass 1，解释追问重跑 Pass 2。
21. SSE 只展示真实节点阶段和安全摘要；最终答案出现后自动收起，不展示隐藏推理。
22. Session/Answer/Dataset/Evidence subject-scoped；AnswerSnapshot 和历史 Dataset 不可变。
23. client_turn_id 幂等；锁 heartbeat；取消、恢复、总轮次超时和 retryable 失败均受控。
24. Composite 每一页 ExecutionRecord 都进入 QA；后续页失败不得漏报。

## 当前验证事实

- Backend：294 tests passed。
- Ruff/format：186 files passed。
- mypy strict：133 source files passed。
- Schema snapshots：41。
- OpenAPI/TypeScript schemas：59。
- Frontend：7 Vitest files / 20 tests passed。
- Chromium E2E：1 journey passed。
- Mock Semantic：sp_eb33e93bdb36bb29；12 文件两次编译逐 hash 一致。
- Real LLM cutover 静态门禁：15/15 passed。
- Mock LLM：RuleBasedMockLLMClient，无外部模型/API；仅用于结构与流程回归。
- CI：Python 3.12、Node 22.17.0、后端/前端/E2E，并含 npm 高危 audit 门禁。

## 已修复的重要根因

- 混合“新分析 + 图表要求”误当纯换图复用；
- Active context 缺 grain；
- Composite 后续页失败未进入 QA；
- 总轮次超时未包住图执行；
- 高基数伪称前端 Top-N/Other；
- 三类 json_repair schema name 冲突风险；
- 审计 model 标识误透传统一 LLM Protocol；
- mcp profile 未校验 non-Mock semantic input；
- Windows Playwright web server 通过后不退出；
- pytest 固定仓库临时目录导致 Windows 锁冲突；
- Agent C required task 覆盖不足；
- 总分析截断/重复和技术明细留在主页面；
- week 被错误编译为 day、统计方法只覆盖部分数值列且未统一应用默认参数/最小样本；
- 统计结论缺少 method/result hash 级证据绑定；
- 纯换图/解释复用没有真正重跑对应 Agent C Pass；逐任务形状未保存在 Active context；
- 显式不兼容图型可能静默丢 task；
- AnalysisPlan、Candidate 和 Claim 的重复/空证据身份缺少确定性拒绝；
- 正式污染扫描范围过窄，未覆盖全部 Agent/Prompt/编排/Query/Analytics/Presentation 路径。

详见 docs/audits/final_end_to_end_audit.md。

## 内网只需要完成

1. Node 22.17.0/Python 3.12/Docker 完整 verify。
2. 注入获准真实 LLM/MCP/身份/证书/Secret。
3. 真实 Excel/Mapping → Semantic Package，可重复编译。
4. 业务 Owner 确认指标、枚举、时区、敏感等级。
5. 15/15 cutover、probe-llm、probe-mcp、只读 smoke。
6. 真实 G01–G25 Shadow、六层 hash、指标重算、Evidence 核对。
7. 真实 Agent A/B/C 的业务质量与动态 Dashboard 验收。
8. Ingress SSE、可信身份、ACL、取消/恢复和上线签字。

完整执行顺序见 docs/integration/INTERNAL_AI_START_HERE.md。不存在已知核心工程 TODO。

## 当前主机边界

- 系统默认 Node 24.14.1；最终验收显式使用隔离的发布锁定 Node 22.17.0，官方完整验包已通过。
- 当前主机无 Docker，未声称真实镜像/profile 运行通过。
- `uv sync --locked`、`npm ci` 与 npm audit 已通过；npm audit 为 0 vulnerabilities。
- 无真实凭证/业务输入，因此不声称真实 LLM/MCP/Shadow 已通过。

## 2026-08-05 Generic Analytics upgrade memory

- Upgrade branch: `MI-GENERIC-ANALYTICS`; reviewed and actual remote baseline were both `dbe31fdc198cbc07975bfcbe20163f647b01aacc` at Phase 0.
- Frozen architecture remains one FastAPI application, one LangGraph StateGraph, Agent A/B/C with C1→Host→C2, compiler-owned DSL, deterministic computation and grounded claims.
- Semantic Package now owns field capabilities plus versioned Metric/Measure/Method/Recipe/Visualization/Entity definitions. Formal filtered-count Metrics explicitly bind a versioned ValueDictionary; no success/failure token assumption remains in Resolver selection.
- Compiler supports all governed field aggregations and emits typed single/multi-value Dataset columns. Terms/composite, budget and dependent-query behavior remain deterministic.
- Analytics adds task/grain/completeness-aware FeatureSummary, generic additive rollup with non-additive rejection, and registered within-group contribution alongside rank/contribution/period/trend/MAD/CV/HHI/Pareto methods.
- Evidence schema is v2. Full merged aggregation JSON, exact downloadable CSV hash, source/calculation/statistical lineage, used-only technical definitions and Claim Trace are persisted in the AnswerSnapshot/artifact system. Artifact reads are answer-owner scoped and detail hits are omitted.
- User Evidence deliberately does not render individual QA pass/fail records. Full QA stays in `AnswerSnapshot.dataset_bundle.data_qa` and internal audit/debug; ERROR/FATAL blocks Agent C/Grounding, while material warnings and reconciliation failures remain visible.
- Internal handoff authority now starts at `docs/internal_handoff/00_START_HERE.md`; production work is limited to real Mapping/catalog/Policy/Metric/Entity, approved LLM/MCP/identity configuration, real Golden and Owner sign-off.
- No database migration was required: metadata remains in immutable snapshot JSON and large JSON content uses `APP_ARTIFACT_DIR/evidence` with ID/path/size/hash validation.
