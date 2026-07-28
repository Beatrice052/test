# Architecture

## 1. 产品边界

这是单体、单 Agent、Mock-first 的 ChatBI POC，不是静态报告，也不是让 LLM
直接操作 OpenSearch 的聊天壳。后端始终拥有字段、查询、权限、指标和结果的
最终控制权。

```text
Browser
  └─ POST /api/chat
       └─ ChatBIAgent
          ├─ LLMClient (Mock or Structured) -> AnalysisPlan
          ├─ SemanticResolver
          ├─ QueryPlanBuilder
          ├─ QueryDslBuilder + QueryDslValidator
          ├─ OpenSearchGateway (Mock or MCP) -> deterministic ToolSelector
          ├─ ResultProcessor + MetricEngine + DataQA
          └─ structured ChatResponse + sanitized Evidence
```

## 2. 三段运行流程

### A. 理解与解析

1. 从 Session 读取最小必要上下文和 pending clarification；
2. Intent Adapter 输出严格 `AnalysisPlan`，不含 Tool、Index 或 DSL；
3. Semantic Resolver 解析指标、字段、时间字段和 Policy；
4. 不明确则保存 pending slot 并提一个澄清问题；
5. blocked/review-required/undefined 在生成 DSL 前结束。

### B. 计划与执行

1. `MonthlyIndexResolver` 将 `[from, to)` 映射到所有相交月份；
2. `QueryPlanBuilder` 生成物理计划，但仍不写 Tool；
3. `QueryDslBuilder` 只生成 OpenSearch Query DSL；
4. Validator 强制只读、Index allowlist、字段 allowlist、无 script、
   无 runtime mapping、时间/桶/返回规模限制；
5. Gateway 根据已确定的 Query 选择 Count、Search 或 Msearch；
6. Mock 或 MCP Gateway 执行同一个契约。

### C. 合并与呈现

1. 多月份先合并原始 count/bucket；
2. Metric Engine 再计算比率，避免平均月度百分比；
3. Data QA 检查 timeout、shard、truncation、count reconciliation 和零分母；
4. QA 失败不输出业务结论；
5. 后端生成结构化 KPI/table/chart/evidence；
6. 前端只渲染，不重新计算指标。

## 3. 为什么当前不用 LangGraph

当前图只有有限、稳定的分支：answered、needs clarification、blocked、
not answerable、QA failed 和 execution failed。没有自主 Tool 探索、循环反思、
长任务恢复或人工审批节点，因此使用显式 `AgentState` 与应用服务更小、更容易
审计和测试。

如果内网阶段引入以下能力，再评估 LangGraph：

- 需要持久化 checkpoint 的长任务；
- 人工审批后恢复；
- 多个可并行且需合并的分析子图；
- 明确受控的重试/补偿边；
- 多模型路由且需要图级可观测性。

即使迁移，现有 `AnalysisPlan`、`QueryPlan`、Gateway、Metric Engine 和 API
契约仍作为节点边界，不允许自由 Tool loop。

## 4. 语义编译

启动时 `SemanticCompiler` 读取：

```text
field_catalog_enrich.csv
mock_mapping.json
metric_registry.yaml
value_dictionary.yaml
policy.yaml
```

Mapping 决定真实物理类型；Catalog 提供描述、别名、字典和使用指导。Mapping-only
字段默认 `review_required`，除非 Policy 显式允许。Catalog-only、Mapping-only、
类型冲突、重复字段和无效指标绑定都会进入 Import Report。

`candidate_role` 在 CSV 入口立即删除，不进入：

- 编译模型；
- hash；
- Retriever；
- Resolver；
- Prompt/context；
- Query DSL；
- Evidence。

## 5. 指标

`failure_rate.v1`：

```text
TotalCount        = 公共过滤后的 document count
TotalSuccessCount = normalized(status) in {SENT, INPROGRESS}
TotalFailedCount  = normalized(status) in {FAILED, ACKFAIL}
OtherCount        = TotalCount - TotalSuccessCount - TotalFailedCount
FailureRate       = ROUND_HALF_UP(100 * TotalFailedCount / TotalCount, 2)
```

`TotalCount=0` 时为 `null`。`status` 在 Mock Executor 中 trim + upper，
空状态不会转换成 `INPROGRESS`。

## 6. 安全

Policy 在四层执行：

1. Retriever/Resolver 不提供 blocked/review-required 候选；
2. DSL Validator 拒绝不允许字段、Index 和语法；
3. Gateway 只暴露允许的只读方法；
4. Evidence Sanitizer 再删除 blocked 字段。

Mock Policy 不是生产安全清单。内网 Mapping 新字段必须先
`review_required`，完成分类后才能改为 allowed。

## 7. Gateway 可替换性

Agent 依赖 `OpenSearchGateway` Protocol，不依赖 Mock 类。

```text
MockOpenSearchGateway ─┐
                       ├─ OpenSearchGateway -> ChatBIAgent
MCPOpenSearchGateway  ─┘
```

`AllowedMCPToolClient` 不定义 Generic API 或 PPL 方法。共享执行器保证 Mock 和
MCP 使用同一 Tool 选择规则。

## 8. LLM 可替换性

Agent 依赖 `LLMClient` Protocol，不依赖具体 provider：

```text
MockLLMClient ───────────────────────────┐
                                        ├─ LLMClient -> ChatBIAgent
Internal provider                       │
  └─ StructuredLLMTransport             │
      └─ StructuredLLMClient ───────────┘
```

`StructuredLLMClient` 只向模型提供 allowed 字段的语义摘要，并使用
`IntentOutcome` JSON Schema 和 Pydantic 再验证。Provider transport 隐藏 SDK、
认证、endpoint 和原始响应。真实模式没有注入时应用启动失败，不回退 Mock。

内网必须先研读批准的参考项目，再实现 transport；详见
`docs/REAL_LLM_INTEGRATION.md`。

## 9. 依赖组装与唯一语义模型

内网运行图：

```text
real Catalog + multi-month Mapping + Metric + Policy
  └─ SemanticCompiler -> CompiledSemanticModel(version/hash)
       ├─ StructuredLLMClient prompt context
       ├─ Retriever/Resolver
       └─ QueryDslValidator

approved LLM client -> StructuredLLMTransport ─┐
approved MCP tools -> AllowedMCPToolClient ────┼─ create_app dependency injection
CompiledSemanticModel ─────────────────────────┘
```

LLM、Resolver 和 Validator 必须使用同一个模型版本。若内网改成运行时获取 Mapping，
应扩展 bootstrap 支持注入 compilation/model，而不是让应用重复编译一份 Mock 模型。

## 10. 前端边界

- Jinja2：只渲染首屏骨架和运行元数据；
- JavaScript：Session、fetch、loading、结构化组件和会话内恢复；
- ECharts：只绘制后端返回的 chart data；
- FastAPI：页面、API、依赖组装和契约校验。

后端不生成 HTML，前端使用 `textContent` 构造内容，不能执行 LLM 输出。

## 11. 内网阶段门禁

内网先完成 I0 认知盘点，再采用 I1～I3：真实 Semantic、真实 LLM + MCP、
指标对账与 POC 验收。Carrier code 在码表就绪时追加；生产化门禁单列为可选
Production。每阶段独立测试和汇报。入口为 `INTRANET_START_HERE.md`，不能跳过
背景/技术方案研读后直接连接真实系统。
