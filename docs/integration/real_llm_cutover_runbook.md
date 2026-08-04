# 真实 LLM 切换与 Mock 规则隔离手册

当前版本：2026-08-04 / MI-NEW。Agent C 当前采用 `post_query_visual_exploration → GovernedVisualizationExplorer → post_query_insight_dashboard` 双阶段；任何只描述旧单阶段 Agent C 的历史文档均已失效。

## 1. 最终结论

内网正式环境不能继续使用 `rule_based`、`fixture` 或 `recorded`。正式配置必须是：

```text
APP_ENV=mcp
CHATBI_IDENTITY_MODE=trusted_headers
CHATBI_LLM_MODE=openai_compatible
CHATBI_GATEWAY_MODE=mcp
CHATBI_SEMANTIC_PACKAGE_DIR=<已审核的非 Mock Semantic Package>
CHATBI_SEMANTIC_INPUT_DIR=<生成该 Package 的已审核非 Mock Semantic Input>
```

项目已经做了三层防误用：

1. `AppSettings` 在 `mcp/prod/production` 环境直接拒绝 Mock Identity、Mock/non-live LLM、非 MCP Gateway 和 Mock Semantic Package；
2. `docker compose --profile mcp` 默认 `openai_compatible` 和 `compiled-semantic/internal`，缺少真实配置时启动失败，不会退回 Mock；
3. `check-real-llm-cutover` 同时检查运行配置和源码依赖边界，只有全部通过才允许进入真实 Shadow。

`rule_based.py` 仍然保留，因为外网/离线测试需要一个无凭证且可重复的 LLM 替身。它是测试实现，不是业务逻辑库，更不是内网上线前的临时生产方案。

## 2. 正式 LLM 到底负责什么

### 2.1 为什么当前 Mock 的“总分析”比较简单

外网默认的 `RuleBasedMockLLMClient` 不是一个可进行开放式数据分析的模型。它的目标是：在没有凭证的环境里稳定产出满足 Agent A/B/C Contract 的结构化对象，以便验证编排、查询、指标、图表、证据和权限链路。它只能从有限的 Dataset 形态中生成整体值、极值、排名、峰值等预设种类的可验证 Claim，不能真正理解任意业务问题，也不能完成以下真实分析能力：

- 根据问题语义判断哪些子问题必须回答、哪些只是可选探索；
- 在多个指标、维度和时间粒度之间判断最有解释力的组合；
- 归纳趋势阶段、结构变化、集中度、异常、分组差异及其业务含义；
- 根据 Business Context 调整结论措辞、优先级与行动建议；
- 对同一份数据生成符合当前问题而非固定模板的完整分析叙事。

因此，Mock 页面可用于验证“系统能否安全走通”，不能作为真实 LLM 分析质量的验收上限。只要 readiness 仍显示 `llm_mode=rule_based`，总分析较机械或较简单就是已知边界，不得通过把更多自然语言规则写进 `rule_based.py` 来伪装成正式智能。

### 2.2 真实 Agent C 的双阶段与总分析强制要求

正式 Agent C 必须先用 `post_query_visual_exploration` 提出 0/1/N 个探索请求；程序生成验证 `VisualizationPreview` 后，再由 `post_query_insight_dashboard` 根据 `AnalysisPlan`、实际 Dataset schema、`FeatureSummary`、MetricDefinition、DataQA 和 Preview 完成 answer-first 分析。两个 operation 都是 strict Schema 调用，不带 tools/tool_choice。完整不变量见 [Agent C 双阶段可视化架构](visualization_agent_architecture.md)。具体要求如下：

1. 逐项覆盖 `AnalysisPlan.tasks` 中所有 `required` task；每个 required task 必须有至少一个可 Grounding 的 Claim，或在 `limitations` 中明确说明为什么证据不足。
2. Claim 数量不固定。只输出与当前问题相关且互不重复的发现；当数据支持用户所问的趋势、比较、集中度、构成、异常或分组差异时，不能只给一句整体值就结束。
3. `primary` Claim 直接回答问题和给出决定性结论；`secondary` Claim 解释重要比较、变化或驱动；`supporting` 只放必要背景。限制和数据质量信息放 `limitations` 或 Evidence，不伪装成业务发现。
4. 所有数字、排名、时间点、类别名和数据依赖判断都必须写成带显式 binding 的 `ClaimDraft`。最终“总分析”只使用通过 `ClaimGrounder` 的 Claim；模型自由文本 `answer_summary` 不能携带未经绑定的数字绕过验证。
5. 禁止输出“分析已完成”“Validated results are ready”一类空泛结论来代替可用发现。若有数据，应陈述实际结果；若无数据或证据不足，应明确说明空结果或限制。
6. Claim 的输出顺序就是总分析的阅读顺序。编排器会纳入全部去重且已 Grounding 的 Claim，不再只截取前三条 primary Claim；已经进入总分析的发现不会在“补充发现”中重复。
7. Pass 1 的图表数量可以是 0/1/N，不得为了“看起来像 Dashboard”固定生成四张图；Pass 2 只能选择 Adapter 返回的 Preview。
8. 每张图必须回答一个不同分析问题，并显式绑定同 task、同 Dataset、同最终 measure 的 Grounded Claim；不能按文字相似度后配结论。
9. 每张图必须有 purpose、grounded findings、最终 encoding 对应的 reading guide 和必要 caveat。
10. 不得将描述性相关或统计异常写成因果结论。行动建议必须与已验证发现相符，并明确其建议性质，不能编造业务原因、Benchmark 或目标值。

真实模型 Shadow 验收必须增加“问题—任务—结论”覆盖矩阵：

| 验收对象 | 必须通过的断言 |
|---|---|
| required task | 在总分析中有对应 Grounded Claim，或在 limitations 中有明确缺口 |
| 总分析 | 直接回答原问题；包含所有材料性发现；无空泛占位语；无重复句 |
| 数字与类别 | 每一项均有 EvidenceRef，可定位 Dataset 行和列 |
| 指标 | 使用受治理 MetricDefinition；率指标可核查分子、分母、排除项与质量状态 |
| 趋势/比较/异常 | 只在 FeatureSummary 和 Dataset 支持时出现；措辞与统计适用性一致 |
| 行动建议 | 能追溯到已验证发现，不引入输入中不存在的业务事实 |
| 图表 | 0/1/N 动态；与 required/recommended task 对应且各自回答不同问题；Preview/Claim 一致性通过 |

如果真实模型只能稳定输出一两句泛化结论，即使 JSON Schema 校验通过，也应判定 Shadow 失败；不得用 Mock 规则补齐分析质量。

### 2.3 “核心指标总览”如何选择指标

核心指标不是前端固定字段，也不是 Dashboard Builder 扫描 Dataset 后“看到什么就放什么”。正式链路如下：

```text
用户问题
  → Agent A 在候选 MetricDefinition 中生成 metric_decisions
  → AnalysisPlan Validator/Resolver 校验 ID、能力与语义范围
  → Agent B 只为任务引用的指标规划查询
  → Metric Engine 按受治理公式计算并完成 QA
  → Dashboard Builder 取“required/recommended ∩ 已注册 MetricDefinition ∩ 已产出有效整体值”
  → 核心指标总览
```

选择规则：

- `required`：直接回答用户明确指标或 required task 所必需的指标；
- `recommended`：对当前问题确有解释价值、且 Agent A 明确选入计划的辅助指标；
- `optional`、`rejected`、`downgraded`：不进入核心指标总览；
- 未注册计算、原始字段、前端临时计算、类别基数和口径排除占比：不得自动升级为核心 KPI；若业务确实需要，必须先成为受治理 MetricDefinition，并由 Agent A 在本轮选择；
- 指标没有可用整体值或未通过对应质量条件时不显示卡片，不能用 0 或猜测值补位；
- KPI 数量完全动态，可以为 0、1 或多个，不设固定四卡模板。

真实 LLM 接入时不得把 `RuleBasedMockLLMClient._select_metric/_overview_metrics` 复制到正式代码。Agent A 应根据用户目标、MetricDefinition 的业务定义、能力、成熟度以及 analytical task 自行输出 `metric_decisions`；确定性组件只负责验证和执行该选择。

### 2.4 主 Dashboard 与“查看证据”的职责边界

主 Dashboard 只保留业务决策信息：总分析、真正相关的 KPI、回答不同问题的图表、用户明确要求或图形不兼容时的业务结果表、必要分析边界和追问建议。

以下内容统一放入“查看证据”，不作为主输出区块：

- OpenSearch 返回的受控原始聚合结果表及各层派生 Dataset；
- 指标公式、实际值、分子、分母、排除项和质量状态；
- DataQA 与 reconciliation 的逐条检查结果；
- 高级角色可查看的实际只读 DSL、执行摘要和 Result Contract。

“数据质量提示”不再以整块模块占据主 Dashboard；KPI 自身仍保留质量状态，完整质量信息在 Evidence 中核查。没有可行图表也不会自动把“聚合明细与指标口径”塞回主页面。只有用户明确要求表格，或某个真实 VisualizationCandidate 需要安全降级时，主页面才显示面向业务的“结果表格”，其技术口径仍在 Evidence。

| 调用 | 正式输出 Contract | LLM 决策 | LLM 明确不做 |
|---|---|---|---|
| Agent A：`turn_and_analysis_plan` | `AnalysisPlanDraft` | 多轮关系、用户意图、指标/维度/时间/任务、显式图表偏好；使用有界字段 description/语义能力/兼容性/画像 | 不查 OpenSearch、不写 DSL、不计算指标、不看 physical path |
| Agent A/B/C 修复：`json_repair` | 原 Draft Contract | 根据结构化错误码修复 Draft 或 Claim/Preview/required-task 覆盖 | 不放宽 Schema、不绕过 Validator |
| Agent B：`logical_query_plan` | `QueryPlanDraft` | 根据 `ResolvedFieldDescriptor` 和任务设计最小充分查询步骤、依赖、grain、result contract、预算内合并策略 | 不输出 physical path、不输出最终 DSL、不调用 MCP |
| Agent C Pass 1：`post_query_visual_exploration` | `VisualizationExplorationDraft` | 基于任务和真实数据形态提出 0/1/N 个探索请求 | 不输出 Claim、数值、代码或任意绘图库 option |
| Agent C Pass 2：`post_query_insight_dashboard` | `InsightDashboardDraft` | 基于真实 FeatureSummary/Preview 的洞察、Claim selector、Preview/Claim 绑定和追问建议 | 不编造数值、不算指标、不输出 ECharts/Plotly option |

下列环节在真实模式中仍必须是确定性程序，不能因为“已经接了大模型”而改成 LLM：

- Semantic Retriever/Resolver、候选 ID allowlist 和 Policy；
- QueryPlan Finalizer、Index Router、DSL Compiler、成本与安全 Validator；
- MCP Gateway 调用、超时、只读边界、分片和响应规模校验；
- Result Parser、Metric Engine、Statistics、Data QA；
- Claim Grounding、图表可行性、去重、Dashboard budget；
- 前端安全图表 option Adapter。

这意味着正式链路是“LLM 做语义与规划，确定性组件做执行与验证”，不是“LLM 直接生成一切”，也不是“把 Mock 的 if/else 搬进编排器”。

### 2.5 Agent A/B 的字段语义和数据充分性

真实 LLM 质量依赖真实字段语义。内网 Excel 的每个字段 description、aliases、business domain、usage guidance 和确认状态必须经过 Semantic Compiler；MCP Mapping 提供 mapping type、aggregatable/searchable/range 能力和跨月兼容性；可选 FieldProfileSnapshot 提供 cardinality、缺失量和范围。Agent A 从有界 CandidateSet 使用这些摘要选择业务字段，Agent B 从 `ResolvedFieldDescriptor` 使用同类事实规划最小充分 grain 和 bucket 预算。

禁止把完整 Excel、完整 Mapping、raw documents、physical path 或 Profile sample_values 直接塞给模型。Profile 只能由 `snapshot-field-profile` 在 staging Policy 生效后生成，固定 `size:0`，再由 Compiler 提取允许进入模型的摘要。正式 cutover 的 Shadow 必须验证：同名/相似字段能靠 description 区分；高基数字段不会生成误导图或超预算 QueryPlan；跨月 PARTIAL/CONFLICT 不会被静默忽略；缺失或未确认 description 会触发澄清/限制而不是猜测。

## 3. 严禁迁移的 Mock 规则

`backend/app/llm/rule_based.py` 中这些函数及其相似逻辑只能用于 Mock：

```text
_analysis_plan
_query_plan
_insight_dashboard
_mock_turn_kind
_time_range
_select_dimensions
_select_metric
_explicit_filters
_failure_filter
_field_matches
_is_time_field / _is_category_field / _is_status_field
```

内网 AI 或开发人员不得做以下操作：

- 把上述函数复制到 `agents/`、`orchestration/`、`query/`、`analytics/` 或 `presentation/`；
- 在正式节点新增 `if "失败原因" in message`、`if "热力图" in message` 等自然语言关键词分支；
- 把 Mock 中出现的 `Channel/Status/Month/SMS/EMAIL` 当作正式默认维度或值；
- 因真实模型输出不稳定，改成“真实 LLM 先调用，失败后静默用 rule_based”；
- 因端点不支持 JSON Schema，改成自由文本后用正则解析；
- 让 Agent B 直接返回 `query_dsl`，或让 Agent/LLM 调 MCP；
- 为通过某一个样例，将普通问题固定成 4 张图、二维图或固定 Dashboard 模板。
- 把 Pass 1 Candidate 和 Pass 2 Claim 分别生成后，用标题/关键词相似度在程序里自动配对。
- 让 Agent C 自由调用 Plotly/ECharts/Python；当前正式 renderer 仍是受控 ECharts Adapter。

允许的 Mock 引用只有 composition root 在 `APP_ENV=mock/local-os` 下选择测试 Adapter。正式 Agent 只依赖 `StructuredLLMClient` Protocol，不得 import 任何具体 Mock class。

## 4. 内网配置步骤

### 4.1 准备运行配置

以 `config/real-llm.env.example` 为模板，通过 Secret Store、Kubernetes Secret 或获准的运行时注入方式配置；不要把真实 Key 写入仓库：

```text
APP_ENV=mcp
CHATBI_IDENTITY_MODE=trusted_headers

CHATBI_LLM_MODE=openai_compatible
CHATBI_LLM_BASE_URL=https://approved-llm.internal/v1
CHATBI_LLM_MODEL=approved-structured-output-model
CHATBI_LLM_API_KEY=<仅运行时注入；若端点要求鉴权>
CHATBI_LLM_TIMEOUT_SECONDS=60

CHATBI_SEMANTIC_PACKAGE_DIR=../compiled-semantic/internal
CHATBI_SEMANTIC_INPUT_DIR=../semantic-input/internal
CHATBI_GATEWAY_MODE=mcp
CHATBI_GATEWAY_CONFIG_PATH=../config/gateway.mcp.yaml
OPENSEARCH_MCP_TRANSPORT=streamable_http
OPENSEARCH_MCP_ENDPOINT=https://approved-opensearch-mcp.internal/mcp
CHATBI_TURN_TIMEOUT_SECONDS=180
```

`CHATBI_LLM_BASE_URL` 指到 OpenAI-compatible `/v1` 根即可，Adapter 会规范化到 `/chat/completions`。不要把 `/chat/completions` 重复拼两次。

### 4.2 确认模型能力

真实端点必须支持：

- OpenAI-compatible Chat Completions；
- `response_format.type=json_schema`；
- `json_schema.strict=true`；
- 当前 Pydantic Contract 生成的嵌套 JSON Schema；
- `temperature=0`；
- 请求超时与服务端取消；
- 中文业务问题和结构化 ID；
- 单次响应完整 JSON，不夹带 Markdown code fence。

本框架不会给 LLM 发送 Tool、MCP handle、数据库连接、凭证或通用 chat escape hatch。若内网代理层不支持 strict JSON Schema，应在 OpenAI-compatible Adapter/代理层修兼容性，不能修改 Agent Contract 为自由文本。

### 4.3 先做静态切换门禁

PowerShell：

```powershell
./scripts/check-real-llm-cutover.ps1 -Output ./reports/real-llm-cutover.json
```

Linux/macOS：

```bash
./scripts/check-real-llm-cutover.sh --output ./reports/real-llm-cutover.json
```

报告必须为 `PASSED`，其中至少包括：

- live environment；
- `openai_compatible` Adapter；
- endpoint/model 已配置；
- trusted identity；
- MCP Gateway；
- 非 Mock Semantic Package；
- 非 Mock Semantic Input；
- 非 `internal-template` Semantic Input/Package；
- 正式 Agent/Prompt/编排/Query/Analytics/Presentation 没有 import Mock/recorded class；
- 编排没有自然语言规则解析器；
- 正式 Agent/Prompt/编排/Query/Analytics/Presentation 没有固定趋势/排名/构成 task bundle；
- Agent A/B/C 四个主 operation 均存在；
- Agent A 与 Plan Validator 使用当前 Semantic Package 的可视化目录；
- Agent B 不拥有 DSL，Compiler 仍拥有 DSL。

当前实现固定为 15 项检查；报告必须 15/15 PASSED。少于 15 项通常表示使用了旧脚本或旧分支，禁止继续切换。

OpenAI-compatible Adapter 的 response schema name 使用 operation + 输出 Contract，例如 `json_repair_AnalysisPlanDraft`、`json_repair_QueryPlanDraft` 和 `json_repair_InsightDashboardDraft`，避免三个修复调用共享同一个 `json_repair` 名称。

报告不会打印 endpoint、Key、prompt、业务数据或响应正文。

### 4.4 再做配置级 LLM 探测

```powershell
./scripts/probe-llm.ps1 -Output ./reports/llm-probe.json
```

探测只发送：

```json
{"probe":"configuration_only","business_data_included":false}
```

它验证 endpoint、model、鉴权和 strict schema，不发送真实问题、Semantic Package 或业务数据。`cutover-check` 和 `probe-llm` 缺一不可：前者检查没有误用 Mock，后者检查真实模型端点确实能工作。

### 4.5 启动后验证 Readiness

```powershell
docker compose --profile mcp up --build
```

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
```

必须看到类似：

```json
{
  "status": "ready",
  "profile": "mcp",
  "llm_mode": "openai_compatible",
  "gateway_mode": "mcp"
}
```

只要 UI 或 readiness 仍显示 `rule_based`、`fixture`、`recorded` 或 `mock`，就没有完成真实切换，禁止开始业务验收。

## 5. 证明三个 Agent（四个主 operation）都真的走了真实 LLM

仅看到 readiness 为 `openai_compatible` 还不够。内网 Shadow 至少执行三类问题：

1. 新问题：验证 `turn_and_analysis_plan` + `logical_query_plan` + `post_query_visual_exploration` + `post_query_insight_dashboard`；
2. 多轮修改：验证 Agent A 判断 FILTER/TIME/DIMENSION/PRESENTATION/EXPLANATION，而不是规则路由；
3. 非固定形态问题：验证 0/1/多图、单维/二维/时间趋势/异常/Pareto/表格可根据真实数据变化。

服务端审计日志应只记录这些安全字段：

```text
correlation_id
turn_id
adapter=openai_compatible
operation
model identifier
latency_ms
attempt
schema_validation=passed|failed
```

不得记录 API Key、Authorization header、完整 prompt、完整用户问题、完整 Semantic 候选、模型原始正文或“思维链”。

推荐验收断言：

- 每个新分析至少出现 Agent A operation；
- 需要新查询时出现 Agent B operation；
- 有验证数据且进入回答阶段时依次出现 Agent C 两个 operation；即使最终是 0 张图，探索 operation 也必须返回合法空 Candidate 集；
- 展示复用场景不执行 Agent B/OpenSearch，但必须有 Agent A 的结构化 turn decision，并执行 Agent C Pass 1；解释复用必须执行 Agent C Pass 2；
- DSL 的 provenance/producer 指向 deterministic compiler，不指向 LLM；
- 指标结果可从 Evidence 中按公式、分子/分母和 Dataset 行重算；
- 真实 LLM 调用失败时返回失败/受控降级，不调用 `RuleBasedMockLLMClient`。

多轮 Shadow 还必须验证逐任务数据签名守卫：dataset、time range、filters 或任一 task 的 metric、dimension、grain、statistical method 变化都必须 requery；只有签名不变的纯展示/解释可复用。总轮次超过 `CHATBI_TURN_TIMEOUT_SECONDS` 必须记录 retryable `TURN_TIMEOUT`，不能继续持锁。Composite 查询的每一页 ExecutionRecord 都必须进入 QA，后续页 shard failure 也必须阻断完整答案。

## 6. Shadow 与 Golden 校准

真实 LLM 是非确定性语义组件，不能用 Mock 的逐字输出作为唯一验收标准。必须分层验证：

| 层 | 核查内容 | 允许差异 |
|---|---|---|
| AnalysisPlan | 意图、指标、维度、时间、任务、图表偏好 | 文案可不同；受治理 ID 与业务含义必须正确 |
| QueryPlan | steps、grain、依赖、预算 | 可安全合并/拆分；不能遗漏 required task |
| Compiled DSL | index/time/filter/agg/size/timeout | 只能由 Compiler 差异产生；不得来自 LLM raw DSL |
| Dataset | 行、列、grain、完整性 | 与相同 DSL 结果一致 |
| Metric/QA | 公式、分子分母、质量状态 | 必须与业务口径精确一致 |
| Insight/Dashboard | 关键发现、Preview/Claim 绑定、数量、每图解释 | 可 0/1/多图；不得重复、误导、错绑或脱离证据 |
| Evidence | 原始检索表、计算、DSL、hash | 必须可追踪、可重算、权限正确 |

先用 `build-shadow-report` 保存各层 hash，再由业务 Owner 对真实口径给出 PASS/FAIL/NEEDS_REVIEW。不要为了让真实结果“看起来像 Mock”而把 Mock 关键词规则移入正式代码。

## 7. 失败与回滚策略

允许回滚到“上一个已批准的真实模型/端点/Prompt 版本”，不允许回滚到 `rule_based` 继续对真实用户服务。

出现以下任一情况必须 fail closed：

- strict JSON Schema 不支持或频繁失败；
- Agent 输出越过候选 ID/预算边界；
- LLM endpoint/model 未配置；
- readiness 不是 `openai_compatible + mcp`；
- `cutover-check` 失败；
- Semantic Package 仍是 Mock；
- 真实 Shadow 指标或证据对账未通过。

紧急情况下可以停止新分析、保留历史不可变答案只读访问；不得静默启用 Mock 产生看似正常但语义不可信的新结果。

## 8. 内网仍需完成的事项

外网框架已经完成 Adapter、Agent Contract、SSE、门禁、测试和文档。内网只需提供/确认：

- 获准的 LLM endpoint、model、网络证书和运行时 Secret；
- 端点对 strict JSON Schema 的真实兼容性；
- 真实 Excel/Mapping 编译出的 Semantic Package；
- failure/status、分子分母、时间字段等业务口径；
- 真实 MCP 只读能力和真实数据 Shadow；
- 反向代理/Ingress 的 SSE 配置与可信身份头；
- 业务 Owner 的 Golden/Shadow verdict。

这些是环境输入和业务确认，不是把核心意图、QueryPlan、DSL、Analytics 或 Dashboard 重新交给内网开发。
