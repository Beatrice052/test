# LLM Adapter 接入指南

> 正式切换必须同时执行 [真实 LLM 切换与 Mock 规则隔离手册](real_llm_cutover_runbook.md)。本页说明 Adapter 协议；切换手册说明防污染门禁、Shadow 和回滚。

## 支持模式

- `fixture`：Golden 精确响应；
- `rule_based`：无模型的完整本地演示和确定性回归；它不是正式意图或 QueryPlan 决策引擎；
- `recorded`：回放已脱敏、经审阅的结构化响应；
- `openai_compatible`：内网 Copilot/获准端点。

三个 Node 可共享一个模型，但使用不同 system prompt 和 Pydantic output schema。Agent C 在同一个有界 Node 内使用探索与综合两个 operation。统一接口只有 `generate()`，operation 只能来自 `ALLOWED_OPERATIONS` 冻结集合；请求没有自由 Tool、MCP、DB、Gateway、Mapping 或通用 chat escape hatch。

正式职责为：Agent A 决定多轮关系、意图、AnalysisPlan 和显式展示偏好；Agent B 决定逻辑 QueryPlan；Agent C Pass 1 基于真实 Dataset/FeatureSummary 动态提出 `AnalyticsToolRequest`（数值列、MethodDefinition、允许参数、分析目的）和可视化探索请求；Host 运行受治理统计工具和 Explorer，Agent C Pass 2 再根据 `AnalyticsToolResult` 与 Preview 决定总体洞察、动态 KPI 和 Preview/Claim 显式绑定。这里的“工具”是模型输出的严格 Contract，由宿主验证后执行，绝不是把函数、代码执行器或数据连接直接交给模型。Finalizer、DSL Compiler、正式 KPI 公式、统计执行、Claim Grounding 和图表可行性校验必须保持确定性。自然语言规则解析只能存在于 `rule_based` Mock Adapter 内，不能成为 `mcp`/生产编排路径。

三个 Agent 可以使用同一个真实模型 endpoint 与 model name，通过不同 system prompt 和 strict output schema 隔离职责，不需要部署三个模型。主编排器是确定性 LangGraph，不得替换成第四个 Supervisor LLM。Agent A 的 candidate metadata 与 Agent B 的 `ResolvedFieldDescriptor` 已包含字段 description、semantic/mapping type、capability、maturity、compatibility 和可选 cardinality；Adapter 不得再把完整 Mapping、physical path、MCP Tool 或 raw documents追加到 Prompt。详见 `multi_agent_orchestration.md`。

`docker compose --profile mcp` 默认 `CHATBI_LLM_MODE=openai_compatible`。endpoint 或 model 未配置时必须 fail fast；`mcp` 与生产环境都会拒绝 `fixture`/`rule_based`/`recorded`，不允许静默降级。

正式环境还会拒绝 Mock Identity、Mock Semantic Package 和非 MCP Gateway。真实 LLM 调用失败时只能失败或进入既有受控 deterministic fallback；严禁回退到 `RuleBasedMockLLMClient` 继续生成正式语义决策。

## 环境变量

```text
CHATBI_LLM_MODE=openai_compatible
CHATBI_LLM_BASE_URL=https://approved-llm.example/v1
CHATBI_LLM_MODEL=approved-structured-model
CHATBI_LLM_API_KEY=<Secret Store 注入，不提交>
CHATBI_LLM_TIMEOUT_SECONDS=30
```

Adapter 将 base URL 规范化到 `/chat/completions`，发送 `response_format.type=json_schema`、Pydantic schema、`strict=true`、`temperature=0`。响应必须通过 strict Contract；HTTP body、Key 和 credentials 不进入异常消息。

## 配置探测

在环境变量就绪后运行：

```powershell
./scripts/probe-llm.ps1 -Output ./reports/llm-probe.json
```

探测只发送 `{"probe":"configuration_only","business_data_included":false}`，验证 endpoint/model/auth/strict schema，不发送业务 Schema、样例值或用户问题。若端点不支持 JSON Schema structured output，应在接入层修正兼容性，不能改 Agent Contract 或放宽成自由文本解析。

在 probe 之前必须先执行：

```powershell
./scripts/check-real-llm-cutover.ps1 -Output ./reports/real-llm-cutover.json
```

该门禁会验证三种真实 Agent operation、Mock import 隔离、Compiler 的 DSL 所有权和非 Mock 运行配置；报告不包含凭证。

## Recorded 模式

`CHATBI_LLM_RECORDING_PATH` 指向与 fixture 相同的 operation→fixture_id→response JSON。录制文件进入仓库前必须脱敏和审阅；真实 prompt、用户数据、Schema 样例和 token 不得直接录制。
