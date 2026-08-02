# 内网 AI 从这里开始：OpenSearch ChatBI V6.1 完整接入与验收手册

## 0. 交付状态与唯一基线

本仓库已经完成外网可完成的核心工程：契约、语义编译、三 Agent 编排、确定性 Query/DSL、MCP Adapter、结果归一化、指标与统计、QA、Grounding、动态 Dashboard、Evidence、会话/权限/幂等/恢复/取消、SSE、前端和自动化测试。

内网不是接手一个半成品，也不需要重新设计 ChatBI。内网只提供无法在外网获得的真实输入、凭证和业务确认，然后用已有脚本完成编译、探测、Shadow 与验收。

唯一权威需求基线：

- docs/baseline/OpenSearch_ChatBI_V6.1_Master_Execution_Spec_含_opensearch-agent_架构校准.md
- SHA-256：3762adc6ca42745151d01894c835f6d80c9dfb84a6e1ce9624e8b026ed85b6c6

若本文、代码注释或历史资料与该文件冲突，以基线为准，并同步修正文档、实现和测试。

## 1. 首次接手的强制阅读顺序

1. 仓库根目录 AGENTS.md：禁止事项和修改门禁。
2. 本文：全流程、真实接入和故障处理。
3. docs/requirements_traceability.md：需求到代码、测试和证据的映射。
4. docs/integration/real_llm_cutover_runbook.md：真实 LLM、Mock 隔离和 Shadow 质量要求。
5. docs/integration/mcp_adapter_guide.md：官方只读 OpenSearch MCP。
6. docs/integration/semantic_schema_guide.md：真实 Excel/Mapping 到 Semantic Package。
7. docs/integration/streaming_progress_design.md：SSE/Ingress。
8. docs/internal_checklist.md：上线签字清单。
9. docs/audits/final_end_to_end_audit.md 与 docs/test_report.md：外网最终审计事实和边界。

不要先改代码。先运行第 3 节离线门禁，并把失败归类为环境问题、真实输入问题或实现缺陷。

## 2. 架构总图与不可合并的对象链

~~~mermaid
flowchart TD
    U["用户问题 / 多轮修改"] --> API["FastAPI + 身份/Session/幂等"]
    API --> A["Agent A：turn_and_analysis_plan"]
    A --> R["确定性 Resolver / Validator"]
    R -->|需要澄清或不可回答| T["终态 AnswerSnapshot"]
    R -->|复用且数据签名一致| REUSE["复用不可变 Dataset/Answer"]
    R -->|需要新查询| B["Agent B：logical_query_plan"]
    B --> F["确定性 Finalizer / Consolidator"]
    F --> CDSL["确定性 DSL Compiler / Validator / Index Router"]
    CDSL --> MCP["只读 OpenSearch MCP Gateway"]
    MCP --> AN["Parser / Normalizer / Composite / Metric / Statistic / QA"]
    AN --> C["Agent C：post_query_insight_dashboard"]
    C --> G["确定性 Grounding / Chart Feasibility"]
    G --> D["Answer-first Dashboard"]
    G --> E["Business / Advanced Evidence"]
    D --> SNAP["不可变 AnswerSnapshot"]
    E --> SNAP
    REUSE --> SNAP
~~~

以下对象层是审计边界，禁止为了“简化”而合并：

~~~text
AnalysisPlan
→ ResolvedAnalysis
→ QueryPlan
→ CompiledQuery
→ ExecutionRecord
→ DatasetBundle
→ ClaimSpec / DashboardSpec / EvidencePackage
→ AnswerSnapshot
~~~

每层都有 object_id、content_hash、provenance 或上游引用。定位问题时从 AnswerSnapshot 反向沿引用检查，不允许直接用最终文案猜测上游行为。

## 3. 接手后先跑离线门禁

发布环境锁定 Python 3.12.x、Node.js 22.17.0；backend/uv.lock、frontend/package-lock.json、docker/mcp/uv.lock 不得绕过。

Windows：

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/verify-package.ps1
~~~

Linux：

~~~bash
./scripts/verify-package.sh
~~~

该门禁负责 lockfile 安装、Ruff、format、mypy、后端全量和 G01–G25、Schema/OpenAPI drift、Semantic compile、前端 lint/type/unit/build、Chromium E2E、Mock readiness。

如果主机暂时不能满足完整环境，必须分层执行并记录缺口：

~~~powershell
cd backend
uv sync --all-groups --locked
uv run ruff check app tests migrations ../scripts
uv run ruff format --check app tests migrations ../scripts
uv run mypy app
uv run pytest -q
cd ..
uv run --project backend python scripts/check_schema_snapshots.py
uv run --project backend python scripts/generate_frontend_types.py --check
uv run --project backend python -m app.cli semantic compile --input-dir semantic-input/mock --output-dir .cache/manual-semantic-check
cd frontend
npm ci
npm audit --audit-level=high
npm run lint
npm run typecheck
npm run test -- --run
npm run build
npm run test:e2e -- --reporter=list --workers=1
~~~

没有 Docker 时，只能声称 Compose YAML、profile 和 binding 通过静态/架构测试，不能声称镜像已经真实构建或真实 MCP 已联通。没有内网网络/Secret 时，不能声称真实 LLM/MCP/Shadow 已通过。

## 4. 从用户提问到最终答案的完整流程

### 4.1 API、身份、Session 与幂等

1. API 从可信身份 Adapter 得到 subject_id/roles。Mock profile 才允许 Mock Identity。
2. Session、Turn、Answer、Dataset、Evidence 的每次读取都带 subject scope；跨用户访问返回拒绝/不存在。
3. client_turn_id 是幂等键。相同已完成请求直接返回原 AnswerSnapshot，不重新查询；执行中的重复请求不创建第二次执行；retryable FAILED 可创建新 Turn 重试。
4. 写锁带 heartbeat；总轮次由 CHATBI_TURN_TIMEOUT_SECONDS 限制；取消会向图执行传播。
5. Checkpoint 和数据库状态用于恢复；历史 AnswerSnapshot 与 Dataset 不可被后续同名逻辑数据覆盖。

### 4.2 请求安全与多轮上下文

请求首先经过确定性策略：raw DSL、写/删索引、Prompt 窃取、越权等请求零查询终止。安全请求加载 ActiveAnalyticalContext。

Agent A 负责判断 NEW_ANALYSIS、NEW_TOPIC、CLARIFICATION、FILTER_CHANGE、TIME_CHANGE、DIMENSION_CHANGE、PRESENTATION_CHANGE 和 EXPLANATION。

复用不是仅看 turn label。Validator 会比较新旧数据签名：

~~~text
dataset_ids + time_range + filters + metric_ids + dimension_ids + grain
~~~

只有签名不变的纯展示/解释才允许零查询复用；任何指标、维度、粒度、过滤或时间变化都会强制 requery。这条守卫防止“问题里同时说了新分析和热力图”时错误复用旧数据。

### 4.3 Semantic Retrieval 与 Agent A

Compiler 从真实 Excel/CSV、Mapping、Registry、Policy 生成 hash 版本化 Semantic Package 和 FTS。运行时 Retrieval 只向 Agent A 提供有界候选，不把整个 Mapping 或字段库塞入 Prompt。

Agent A 的正式 operation 是 turn_and_analysis_plan，输出 AnalysisPlanDraft。它负责：

- 多轮关系与执行模式建议；
- 问题原型和分析目标；
- 数据集、时间范围、过滤、维度、粒度；
- 每个受治理 MetricDefinition 的 required/recommended/optional/rejected/downgraded 决策及原因；
- 0/1/N 个分析任务、优先级、期望统计方法和 visualization intent；
- 用户明确指定的图表/表格偏好；目录外类型进入 unsupported_chart_label。

它不能决定物理字段、索引、最终查询步骤、DSL、指标公式或数据结果。

AnalysisPlan Validator 只接受候选 ID，校验时间半开区间、预算、能力、指标成熟度、任务覆盖和多轮一致性；最多进行有界 json_repair，仍失败则受控终止，不放宽 Schema。

### 4.4 Agent B、QueryPlan 与 DSL

Agent B 的 operation 是 logical_query_plan，输出 QueryPlanDraft。它根据已解析 ID 负责 QueryStep 数量、依赖关系、每步目标、维度、粒度、指标、ResultContract、可合并查询和必要的 dependent query。

Agent B 不知道 MCP Tool、endpoint、物理字段路径，也不能输出 JSON DSL。

之后全是确定性组件：

1. QueryPlan Finalizer 校验 required task 覆盖、依赖、预算、ResultContract。
2. Consolidator 合并可共享的数据需求，避免“一图一查”。
3. Index Router 根据时间范围和 Mapping history 路由索引。
4. DSL Compiler 从白名单 AST 生成最终只读 DSL。
5. Validator 检查 index/time/filter/aggregation/size/script/write/预算。
6. CompiledQuery 记录 semantic package、metric、timezone、query plan 和 producer。

### 4.5 MCP、执行与多页结果

正式数据路径只使用批准的官方 OpenSearch MCP Adapter。启动时 Capability Probe 验证 required/forbidden bindings；不绑定 Generic API、PPL、Memory 或写 Tool。

Gateway Executor 负责超时、有限重试、响应大小、取消、调用次数和 ExecutionRecord。Composite aggregation 可分页到 CHATBI_MAX_COMPOSITE_PAGES；所有页的 timeout、shard failure、timed_out 和完整性都会进入 QA，不能只检查第一页。

### 4.6 Analytics 与 QA

Raw Result Parser 和递归 Bucket Normalizer 把 OpenSearch 返回转换为稳定 TabularDataset：

- 保留 QueryPlan 约定的全部维度；
- 稳定 row_id；
- 明确 grain、columns、completeness、source；
- 同一个高信息 Dataset 可派生 trend、ranking、composition、Pareto、pivot 等，不重复查询。

Metric Engine 只使用受治理公式。率指标必须保存 numerator、denominator、excluded、minimum denominator 和质量状态；前端不计算。Statistic Engine 按 MethodDefinition 执行 total/share/delta/rank/peak/trend/concentration/anomaly 等确定性方法。

DataQA 与 Reconciliation 覆盖 shard failure、timeout、空/部分结果、小计与总计、率值/分母/排除项、grain/维度、composite 页面、高基数、Mapping 和 timezone。Fatal QA 阻止业务分析；可接受 partial 必须显式标记。

### 4.7 Agent C、总分析与动态 Dashboard

Agent C 的 operation 是 post_query_insight_dashboard，输入只包含 AnalysisPlan、Dataset schema、受控 FeatureSummary、MetricDefinition 视图、DataQA、VisualizationDefinition 和预算，不读取原始明细，不执行查询。

它负责：

- 为每个 required task 提出 ClaimDraft，或在 limitations 中写明证据缺口；
- 组织 primary/secondary/supporting 的 answer-first 阅读顺序；
- 使用 selector grammar 引用 Dataset 行列，不能自己写数字；
- 根据真实任务、粒度、基数、完整性和用户偏好提出 0/1/N 个 VisualizationCandidate；
- 每张图回答不同问题；
- 给出必要且可追溯的后续建议。

ClaimGrounder 将 selector 解析为真实 Dataset 行列，绑定 EvidenceRef，拒绝未绑定数字、未知 task、未知列、错误 selector 和重复结论。总分析只由已 Grounding Claim 组成，不相信模型自由文案中的数字。required task 缺失会触发 Agent C 有界修复；仍失败则 PARTIAL 并带限制。

Dashboard Builder 的规则：

- 第一块是直接回答/总分析；已在总分析中的发现不再重复为“关键发现”；
- KPI 只来自本轮 AnalysisPlan 中 required/recommended 且已计算有效的 MetricDefinition；
- KPI、图表和区块数量均允许 0/1/N，不固定四个；
- 图表类型由 Agent C 候选 + Visualization Registry + Dataset 形态共同决定；
- 用户明确指定类型时兼容则采用，不兼容则解释并降级表格；
- 完整高基数数据也不会伪造前端 Top-N/Other 变换；超出可读上限直接安全降级表格；
- 页面不显示整块技术 QA 或“聚合明细与指标口径”。

当前安全渲染目录包括 bar、line、heatmap、stacked_bar、donut、dot、pareto、table、pivot；这不是 Agent 固定选图模板，而是防止任意 ECharts/JavaScript 注入的可扩展白名单。新增图种必须同时新增 Contract、Registry、后端可行性、前端安全适配和测试，不能只让 LLM 输出新字符串。

### 4.8 Evidence 分层

Business Evidence 面向普通业务用户，依次展示：

1. OpenSearch 返回的受控原始聚合表和派生 Dataset；
2. 指标定义、公式、值、分子、分母、排除项、质量；
3. DataQA 与 Reconciliation；
4. 来源、时间范围、时区、完整性和 hash。

Advanced Evidence 仅授权角色可见，包含最终只读 DSL、执行摘要、ResultContract 和技术 lineage。Debug 默认关闭。内部 Agent JSON、Prompt、隐藏推理、Secret、完整原始模型正文不进入 Evidence。

### 4.9 SSE 用户体验

/chat/stream 从实际 LangGraph 节点完成事件产生请求/权限、上下文、Agent A、Agent B、DSL 编译、OpenSearch、Analytics/QA、Agent C/Dashboard 和完成/失败阶段。

这些是可审计阶段，不是模型隐藏思维链。禁止流式输出 Prompt、完整用户问题、原始 DSL（业务层）、凭证或私有推理。最终 AnswerSnapshot 到达后，前端自动清除/收起临时进度；刷新只恢复最终不可变答案。

## 5. Mock LLM 到底是什么

当前无凭证测试使用 RuleBasedMockLLMClient。它不是外部模型，也不调用任何 LLM API；它用确定性规则构造满足 Agent A/B/C Schema 的测试对象。

它只用于证明编排、Query/DSL/Analytics/QA/Evidence、多轮、恢复、权限、幂等、动态 Dashboard 和各层 Contract 能安全走通。它不能证明真实自然语言理解或开放式分析质量。Mock 总分析较机械是预期边界。不得通过继续增加关键词规则来“改善智能”，更不得把这些规则迁入正式路径。

## 6. 真实 LLM 的精确接入

复制 config/real-llm.env.example 到 Secret/运行配置系统，不提交真实值。正式关键配置：

~~~text
APP_ENV=mcp
CHATBI_IDENTITY_MODE=trusted_headers
CHATBI_LLM_MODE=openai_compatible
CHATBI_LLM_BASE_URL=<approved endpoint>
CHATBI_LLM_MODEL=<approved strict-output model>
CHATBI_LLM_API_KEY=<runtime secret>
CHATBI_SEMANTIC_PACKAGE_DIR=../compiled-semantic/internal
CHATBI_SEMANTIC_INPUT_DIR=../semantic-input/internal
CHATBI_GATEWAY_MODE=mcp
OPENSEARCH_MCP_ENDPOINT=<approved read-only MCP>
CHATBI_TURN_TIMEOUT_SECONDS=180
~~~

Adapter 发送 chat-completions 兼容请求，使用 strict JSON Schema response_format。Schema name 按 operation + 输出 Contract 区分；三种 json_repair 也不会共用一个冲突名称。请求中没有 tools/tool_choice。

真实运行包含六类调用：

| operation / schema name | 输出 | 责任 |
|---|---|---|
| turn_and_analysis_plan | AnalysisPlanDraft | Agent A：意图、多轮、指标、维度、任务、展示偏好 |
| json_repair_AnalysisPlanDraft | AnalysisPlanDraft | 只修复 Agent A Contract 错误 |
| logical_query_plan | QueryPlanDraft | Agent B：逻辑查询步骤、依赖、粒度、ResultContract |
| json_repair_QueryPlanDraft | QueryPlanDraft | 只修复 Agent B Contract 错误 |
| post_query_insight_dashboard | InsightDashboardDraft | Agent C：已验证证据上的洞察绑定与图表候选 |
| json_repair_InsightDashboardDraft | InsightDashboardDraft | 只修复 Grounding/required-task/Schema 错误 |

切换前运行：

~~~powershell
./scripts/check-real-llm-cutover.ps1 -Output ./reports/real-llm-cutover.json
./scripts/probe-llm.ps1 -Output ./reports/llm-probe.json
~~~

cutover-check 有 12 项：正式环境、live adapter、endpoint、model、可信身份、MCP gateway、非 Mock semantic package、非 Mock semantic input、Mock import 隔离、无正式文本意图解析器、三 Agent operation、Compiler 独占 DSL。任一失败禁止 Shadow。

probe-llm 只发无业务数据的最小 strict-schema 探针；它证明端点、鉴权、模型和 Schema 能工作，但不能代替业务 Shadow。

真实 LLM 的质量要求：

- Agent A 必须根据真实问题和候选语义决定，而不是复刻 Mock 关键词；
- Agent B 必须覆盖 required tasks，保持 grain/result contract，并让 Compiler 独占 DSL；
- Agent C 必须完整回答 required tasks，不能只写“分析完成”；
- 所有数字、类别、排名、时间和数据依赖判断必须通过 Claim binding；
- 模型失败只能 fail/受控 PARTIAL，不得调用 RuleBasedMockLLMClient；
- repair 只能根据结构化错误码修复原 Contract，不能扩大 ID、预算或权限。

## 7. 真实 MCP 与 Semantic Package

### 7.1 探测 MCP

~~~powershell
./scripts/probe-mcp.ps1 -Config ./config/gateway.mcp.yaml -Output ./reports/mcp-probe.json
~~~

必须确认 required tools 存在、forbidden tools 未绑定、只读、响应 Contract 和超时符合配置。

### 7.2 固化 Mapping

~~~powershell
./scripts/snapshot-mapping.ps1 -Config ./config/gateway.mcp.yaml -Dataset <dataset_id> -Index <index-2026.05>,<index-2026.06>,<index-2026.07> -Output ./input-real/mapping_snapshot.json
~~~

索引必须逐个显式列出；不要用未审核的宽泛通配符替代审计快照。

### 7.3 生成候选输入

~~~powershell
./scripts/prepare-internal-input.ps1 -FieldCatalog ./input-real/field_descriptions.xlsx -Mapping ./input-real/mapping_snapshot.json -OutputDir ./semantic-input/internal -IndexPattern 'approved-index-*'
~~~

该步骤复制 internal-template，并默认只启用无需争议的 message_record_count。failure_rate 在业务确认前保持不可执行。

### 7.4 确认 failure_rate

只有业务 Owner 明确签字 success/failure/pending/unknown/null、minimum denominator、owner 后才运行：

~~~powershell
./scripts/configure-failure-rate.ps1 -InputDir ./semantic-input/internal -SuccessStatus @('SUCCESS') -FailureStatus @('FAILED','ERROR') -PendingStatus @('PENDING') -UnknownStatus @('UNKNOWN') -NullGroup unknown -MinimumDenominator 30 -Owner '<business-owner>'
~~~

示例值不能直接用于生产。必须与真实枚举和业务定义一致。

### 7.5 编译两次并比较

~~~powershell
./scripts/compile-internal-semantic.ps1 -InputDir ./semantic-input/internal -OutputDir ./compiled-semantic/internal-a
./scripts/compile-internal-semantic.ps1 -InputDir ./semantic-input/internal -OutputDir ./compiled-semantic/internal-b
~~~

两次 package_version、文件清单和内容 hash 必须一致；Import Report 必须 PASSED；任何冲突、模糊字段、跨月不兼容 Mapping、未确认指标或敏感字段错误都要先修真实输入，不能绕过 Compiler。

审核通过后，把批准产物固定到正式 compiled-semantic/internal，保留原输入版本、owner、日期和审批记录。

### 7.6 固定只读 Smoke

~~~powershell
./scripts/smoke-mcp.ps1 -Config ./config/gateway.mcp.yaml -Dataset <dataset_id> -Index <index-2026.05>,<index-2026.06>,<index-2026.07> -TimeField <time_field> -ChannelField <channel_field> -StatusField <status_field> -From '2026-05-01T00:00:00+08:00' -To '2026-08-01T00:00:00+08:00' -Timezone 'Asia/Hong_Kong' -Output ./reports/mcp-smoke.json
~~~

检查时间半开区间、月份索引、维度保留、shard failure、timeout、返回大小和只读性。

## 8. 真实 Shadow 与业务验收

至少覆盖：

- 单值、单维排名、多维 month×category；
- 日/周/月趋势；
- 率指标及分子/分母/排除项；
- Top N 依赖；
- 构成、Pareto、异常、明细；
- 追问：过滤/时间/维度/换图/解释/新主题；
- 0/1/N 图、显式图表请求和不兼容降级；
- 空结果、部分 shard、超时、高基数、跨月 Mapping、时区边界；
- raw DSL/写请求/越权/Prompt injection；
- 幂等、跨用户隔离、刷新恢复。

每个 Case 保存六层脱敏工件：

~~~text
analysis_plan
query_plan
compiled_dsl
normalized_dataset
metric_result
dashboard_evidence
~~~

生成 hash 报告：

~~~powershell
./scripts/build-shadow-report.ps1 --case-id G-REAL-001 --analysis-plan <path> --query-plan <path> --compiled-dsl <path> --normalized-dataset <path> --metric-result <path> --dashboard-evidence <path> --classification UNKNOWN_NEEDS_INVESTIGATION --business-verdict NEEDS_REVIEW --require-ratio-evidence --output-dir ./reports/internal
~~~

率指标必须启用 --require-ratio-evidence。classification 用于解释新旧差异；business-verdict 必须由 Owner 给出。报告只保存路径名、大小和 SHA-256，不复制敏感 payload。

真实 LLM 质量不能用“JSON 合法”代替。Agent C 必须完整回答 required tasks；总分析不能只有“分析已完成”；所有数字/类别/排名必须 Grounding；图表数不固定；结论与建议不能超出证据；相关性不得写成因果。

## 9. 正式启动与运行检查

确认所有 Secret 通过运行时注入后：

~~~bash
docker compose --profile mcp up --build
~~~

Readiness 必须同时显示：

~~~json
{
  "status": "ready",
  "profile": "mcp",
  "llm_mode": "openai_compatible",
  "gateway_mode": "mcp"
}
~~~

只要出现 rule_based、fixture、recorded、Mock Identity、Mock Semantic 或非 MCP gateway，就没有完成正式切换。

Ingress 对 text/event-stream 必须关闭 buffering/cache/压缩聚合，read timeout 大于总轮次超时，并传播客户端断连。参考 frontend/nginx.conf 和 docs/integration/streaming_progress_design.md。

## 10. 可观测性与隐私

允许的 LLM 审计字段：

~~~text
correlation_id
turn_id（若上下文可得）
adapter
operation
model
duration_ms
attempt
schema_validation
status
error_type
~~~

禁止记录 API Key、Authorization、Prompt、完整用户问题、完整候选、原始模型正文、数据行、DSL、MCP endpoint/Secret。新增日志字段必须经过 allowlist。

监控至少包含：turn latency、各 operation latency/Schema failure、repair rate、MCP timeout/retry/shard failure、QA fatal/partial、Grounding reject、required-task coverage、fallback、cancel/recovery、SSE disconnect。

## 11. 故障分类与允许动作

| 现象 | 首先检查 | 允许动作 | 禁止动作 |
|---|---|---|---|
| LLM strict Schema 失败 | probe、模型能力、response_format、schema name | 修 Adapter 兼容或换批准模型 | 自由文本解析、切 RuleBased |
| Agent A 选错指标/意图 | 真实候选、Prompt、Shadow task | 调整 Prompt/候选语义并回归 | 在编排中加关键词规则 |
| Agent B QueryPlan 不完整 | required task、grain、ResultContract | 改 Agent B Prompt/Validator | 让 LLM 输出 raw DSL |
| DSL 错误 | Finalizer/Compiler/Mapping | 修确定性 Compiler/Mapping + 测试 | 把 DSL 交给 LLM |
| 指标不一致 | MetricDefinition、分子分母、排除项 | 业务确认后版本化 Metric | 前端临时算、口头解释 |
| 图表不合适 | task、Dataset grain/cardinality、Registry | 调整 Agent C/Registry/Validator | 固定四图、任意 option |
| 总分析简单 | Agent C required-task 覆盖、FeatureSummary | 优化真实 Agent C Prompt/模型并 Shadow | 向 Mock 加业务规则 |
| Evidence 看不懂 | Business/Advanced 分层 | 改展示映射，不改事实对象 | 把 Agent JSON 直接展示 |
| 纯换图触发查询 | data signature、turn decision | 修复复用守卫与回归 | 用字符串特判单个问句 |
| 超时/部分分片 | ExecutionRecord 全页 QA | 失败或明确 partial | 当作完整答案 |

## 12. 仍需要内网 AI 做的事

这是完整清单，不允许扩张为“重写核心系统”：

1. 在 Node 22.17.0、Python 3.12、Docker 环境运行完整离线门禁。
2. 注入获准 LLM/MCP/身份/证书/Secret，运行 12 项 cutover、LLM probe、MCP probe。
3. 导入真实字段说明和 Mapping；确认敏感字段、时区、粒度、索引覆盖。
4. 由业务 Owner 确认 failure/status 与所有真实指标口径并版本化。
5. 重复编译并审核真实 Semantic Package。
6. 运行固定只读 MCP smoke。
7. 运行真实 G01–G25 扩展 Shadow；保存六层 hash、重算指标、核对 Evidence。
8. 验收真实 Agent A/B/C：意图/QueryPlan/分析完整性/动态可视化，不迁移 Mock 规则。
9. 验证生产 Ingress SSE、可信身份头、Evidence ACL、跨 subject 隔离、取消与恢复。
10. 获得业务 Owner、数据 Owner、安全/运维 Owner 的最终 verdict，按 Checklist 切换。

若这些步骤之外还需要核心代码修改，必须先提供可复现 Case、失败层、期望 Contract 和回归测试，再做最小根因修复；禁止针对截图或单一问句东拼西凑。

## 13. 上线停止条件与回滚

出现任一项必须停止新分析：

- cutover/probe 未通过；
- Semantic Import Report 非 PASSED；
- Mock 污染正式路径；
- LLM 不支持 strict Schema；
- required task 大面积缺失；
- 指标/证据无法重算；
- shard failure 被当作完整；
- 越权、写 Tool、raw DSL 或 Prompt 泄露；
- SSE 代理导致用户长期无进度且无法取消；
- 业务 Owner 未签字。

可以回滚到上一个批准的真实模型、Prompt、Semantic Package 或 MCP 配置；不能回滚到 RuleBased 为真实用户继续生成新答案。历史不可变 AnswerSnapshot 可继续只读访问。

## 14. 最终交接检查表

| 检查 | 通过证据 |
|---|---|
| 唯一基线未漂移 | 基线 SHA-256 与本文一致 |
| 离线工程完整 | verify-package 通过 |
| Semantic 可复现 | 两次版本、清单、hash 一致 |
| 正式路径无 Mock | 12/12 cutover PASSED |
| LLM 真可用 | probe-llm PASSED，三 Agent 审计 operation 可见 |
| MCP 真可用且只读 | probe-mcp 与 smoke PASSED |
| 指标可信 | Owner 口径 + 分子分母重算 + QA |
| 分析完整 | required task → grounded claim/limitation |
| Dashboard 动态 | 多种问题得到 0/1/N 不同视图，显式偏好可识别 |
| Evidence 可检查 | 聚合表、计算、QA、授权 DSL 均可回溯 |
| 多轮正确 | 纯展示复用；数据签名变化重查 |
| SSE 友好安全 | 阶段实时、最终收起、断连可取消、无私有推理 |
| 安全与恢复 | owner scope、幂等、取消、超时、恢复、只读 |
| 业务可上线 | Shadow/Golden/Owner verdict 完整 |
