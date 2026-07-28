# OpenSearch ChatBI 外网技术执行规格

**版本：** external-mock.v1

**状态：** 外网可实现范围已完成；已建立内网 AI 接棒与真实依赖注入边界

**业务时区：** Asia/Hong_Kong

> 内网接手必须先阅读 `INTRANET_START_HERE.md`、本规格、架构和决策日志，完成
> I0 盘点后按 I1～I3 执行。不能直接将 Mock client 替换成未经现场 schema
> 验证的调用。

## 1. 目标

构建可实际操作的 ChatBI POC。用户在聊天页面自然语言提问，系统返回总结、KPI、
表格、图表、指标口径、警告和 Evidence。结果必须来自完整后端链路，不允许前端
硬编码，也不允许 LLM 直接生成 HTML、DSL 或自由选择 Tool。

## 2. 三段主流程

```text
理解
  Intent Adapter -> AnalysisPlan -> Semantic Resolver -> clarification/policy

执行
  Monthly Index -> QueryPlan -> Query DSL -> Validator -> Gateway ToolSelector

呈现
  Raw merge -> Metric Engine -> Data QA -> structured response -> browser render
```

### 2.1 理解阶段

- 输入：当前问题 + pending clarification 的最小上下文；
- 输出：严格 Pydantic `AnalysisPlan`；
- 不包含：MCP Tool、物理 Index、Query DSL；
- 语义层解析默认时间字段、指标版本、维度、filter 和字段操作；
- 歧义只问一个可操作的澄清问题；
- blocked/review-required 不进入下一阶段。

### 2.2 执行阶段

- 时间区间统一为 `[from, to)`；
- 根据用户时间选择全部相交的 `tbl_os_sub_message_YYYY_MM`；
- QueryPlan 与 Tool 分离；
- DSL 仅允许只读 Query DSL；
- Validator 后才允许 Gateway 执行；
- ToolSelector 是程序规则，不是 LLM：

| 需求 | 能力 |
|---|---|
| 单一 document count | CountTool |
| 过滤、聚合、趋势、Top N | SearchIndexTool |
| 多个独立物理查询 | MsearchTool |
| Index inventory | ListIndexTool 对应 `list_indices` |
| Mapping | IndexMappingTool 对应 `get_mapping` |
| Generic API / PPL | 禁止 |

### 2.3 呈现阶段

- 跨月先合并 raw count/bucket，再计算百分比；
- Metric Engine 是唯一公式实现；
- QA 失败不返回业务结论；
- Evidence 只含安全清理后的计划和摘要；
- 前端只显示后端数值，不实现第二套公式。

## 3. 技术栈与职责

| 技术 | 职责 |
|---|---|
| FastAPI | API、页面路由、应用依赖组装、请求/响应校验 |
| Pydantic | AnalysisPlan、QueryPlan、Semantic、API、Session 契约 |
| Jinja2 | 首屏 HTML 骨架和运行元数据 |
| Vanilla JavaScript | chat、fetch、loading、sessionStorage、组件渲染 |
| ECharts 6.1.0 | 本地 bar/line 图表，不计算指标 |
| YAML/CSV/JSON | 可替换语义源、Metric 和 Policy |
| pytest/Ruff/Pyright | 行为、风格和类型质量门 |

### 3.1 LangGraph 决策

当前不使用 LangGraph。原因不是省略 Agent 设计，而是该 POC 明确禁止自由 Tool
循环，只有有限状态和确定性边。采用显式 `AgentState` 更容易审计和验证。

未来出现 checkpoint、人工审批恢复、复杂并行子图时可引入 LangGraph，但必须
复用现有严格契约，不能让模型绕过 Gateway/Policy。

### 3.2 LLM 决策

外网默认使用 `MockLLMClient`，它是确定性的 bounded intent adapter，不需要银行
数据或模型凭证。代码同时提供 `StructuredLLMClient` 和
`StructuredLLMTransport` 的真实接入契约：

```python
create_analysis_plan(question, context) -> IntentOutcome
summarize(question, prepared_data, caveats) -> str
```

内网替换模型时：

- 先研读一个批准的内网参考项目，采用其 client/factory、认证、超时、重试、
  structured output、审计和日志脱敏惯例；
- 使用 JSON schema/structured output；
- Prompt 只含 allowed 字段的语义摘要；
- blocked 字段永不进入 Prompt；
- 模型只能输出 AnalysisPlan 和总结；
- QueryPlan、Tool、DSL、公式继续由程序控制；
- 输出必须经 Pydantic 验证和 answerability。

使用 `CHATBI_INTENT_BACKEND=structured_llm` 时必须显式注入真实 `LLMClient`，
缺少实现会启动失败，不允许回退 Mock。完整要求见 `docs/REAL_LLM_INTEGRATION.md`。

## 4. 后端模块

| 模块 | 关键职责 |
|---|---|
| `agent/contracts.py` | AnalysisPlan、QueryPlan、Evidence |
| `agent/state.py` | 有限状态和合法转移 |
| `agent/service.py` | 唯一 ChatBI 主流程 |
| `semantic/compiler.py` | CSV/Mapping/Metric/Policy 编译 |
| `semantic/retriever.py` | allowed 字段确定性候选 |
| `semantic/resolver.py` | 字段、指标、歧义、Policy |
| `intent/mock_client.py` | 外网 bounded AnalysisPlan adapter |
| `intent/structured_client.py` | 真实 LLM strict adapter 与 provider transport 契约 |
| `query/index_resolver.py` | `[from,to)` 到月份 Index |
| `query/planner.py` | 物理 QueryPlan |
| `query/dsl.py` | OpenSearch Query DSL |
| `query/validator.py` | 只读、字段、Index、限制 |
| `gateway/execution.py` | 确定性 ToolSelector 和执行记录 |
| `gateway/mock.py` | JSONL Mock OpenSearch |
| `gateway/mcp.py` | 内网 MCP 五项窄接口 seam |
| `metrics/engine.py` | versioned deterministic metric |
| `results/processor.py` | 跨分区合并和展示数据 |
| `results/qa.py` | timeout/shard/truncation/reconciliation |
| `sessions/store.py` | TTL/LRU/容量/消息上限 |
| `api/routes.py` | Chat/health/reset/admin |

## 5. 前端页面

```text
Mock 数据警示
Header：项目名、Mock Connected、阶段
Runtime：数据源、可用月份、默认时间、时区、模型
左侧：5 个示例、当前口径
右侧：
  会话历史
  assistant summary
  KPI cards
  metric version
  ECharts
  table
  warnings
  collapsed Evidence
  composer/loading/reset
Footer：被禁止的能力
```

所有动态文本使用 `textContent`，不执行后端/LLM HTML。

## 6. API

主入口：

```text
POST /api/chat
```

输入：

```json
{"session_id":"session-001","message":"2026年7月各Channel的Failure Rate是多少？"}
```

状态：

```text
answered
needs_clarification
blocked
not_answerable
error
```

详细契约见 `docs/API.md`。

## 7. Mock 范围

- 2026-06：180 docs；
- 2026-07：186 docs；
- 2026-08：186 docs；
- 合计 552 docs；
- 三个 Channel、三个 Route、三个 synthetic provider；
- 状态含成功、失败、Other、null、trim/case 变体；
- 含 retry、重复 document、空结果和值歧义；
- 含 6 个 blocked 字段用于泄露回归测试；
- 含 mapping-only、catalog-only、review-required。

详细字段见 `docs/MOCK_DATA_DICTIONARY.md`。

## 8. 多轮状态

Session 保存：

```text
session_id
bounded message history
pending clarification
last AnalysisPlan
last QueryPlan
last run_id
updated_at
```

pending clarification 保存原始问题、缺失 slot、允许选项和 partial plan。下一轮
只组合原问题与当前答案，不把全部历史无限送入模型。默认 TTL 30 分钟，容量 200，
每会话最多 30 条消息。

## 9. Failure Rate

```text
failure_rate.v1
TotalCount        = document count
TotalSuccessCount = normalized(status) in {SENT, INPROGRESS}
TotalFailedCount  = normalized(status) in {FAILED, ACKFAIL}
OtherCount        = TotalCount - TotalSuccessCount - TotalFailedCount
FailureRate       = ROUND_HALF_UP(100 * TotalFailedCount / TotalCount, 2)
```

零分母返回 `null`；retry、重复和空/未知状态保留在分母。

`statusCode` 的运营商规则尚未确认。外网对移动/电信/联通专项失败率返回
`not_answerable`，内网设计见 `docs/INTERNAL_MIGRATION.md`。

## 10. Policy

Mock blocked：

```text
messageBody
customerName
phoneNumber
emailAddress
bankAccount
customerId
```

Policy 在 Retriever、Resolver、Validator、Gateway 和 Evidence 多层执行。
当前不声称这是生产敏感字段清单。

## 11. 验收

自动化：

```text
108 tests passed
Ruff passed
Pyright 0 errors / 0 warnings
JavaScript syntax passed
```

浏览器：

- 完整 Chat 页面加载；
- Mock/Index/时间/模型可见；
- KPI、3 行表格、ECharts canvas 渲染；
- Evidence 默认折叠、8 个区块可展开；
- 多轮澄清续答；
- 空结果无图；
- Policy 阻断无 Evidence；
- Session 刷新恢复；
- 无页面级横向溢出；
- 控制台无 error/warning。

## 12. 外网后仍待内网确认

这些事项不阻塞 Mock，但阻塞生产：

1. 全量真实 Mapping 和物理时间字段；
2. Catalog 的真实业务语义、值字典和字段 owner；
3. `status` 与真实报表逐日/逐维度对账；
4. `statusCode/status_code` 的三运营商编码规则；
5. 生产 blocked/review-required/RBAC；
6. MCP 工具请求/响应和 partial error 结构；
7. 内网 LLM provider、model、超时和审计策略；
8. 生产 Session 存储、认证、限流和日志脱敏；
9. 指标版本发布与历史生效规则；
10. 性能、桶规模和跨月查询上限。

## 13. 内网接棒执行模型

```text
I0  研读项目背景/技术方案，盘点真实来源
I1  真实 Catalog + MCP Mapping 校验 + POC access
I2  真实 LLM transport + OpenSearch MCP 五项窄能力 + /api/chat 联调
I3  Failure Rate 对账 + POC 最终验收；码表就绪时追加 Carrier 指标
Optional Production  Policy/RBAC、认证、持久化、审计和生产压测
```

生产 Policy/RBAC 属于可选生产化工作，不阻塞 I1～I3；这些阶段使用 Catalog 的
access/sensitivity 和现有技术 Policy，并明确标记 pending。

内网只应替换/扩展：

```text
semantic sources 和编译输入
StructuredLLMTransport
AllowedMCPToolClient
Metric/Policy 配置
应用依赖组装
生产 Session/认证/审计/部署
```

不得因接真实依赖重写 AnalysisPlan、QueryPlan、Agent 主流程、API 或前端。真实
Semantic Model 必须由 LLM、Resolver 和 Validator 共用同一版本。

专项文档：

- `docs/INTRANET_AI_HANDOFF.md`
- `docs/REAL_SEMANTIC_ONBOARDING.md`
- `docs/REAL_LLM_INTEGRATION.md`
- `docs/REAL_OPENSEARCH_MCP_INTEGRATION.md`
- `docs/INTRANET_EXECUTION_CHECKLIST.md`
