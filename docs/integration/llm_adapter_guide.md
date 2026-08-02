# LLM Adapter 接入指南

> 正式切换必须同时执行 [真实 LLM 切换与 Mock 规则隔离手册](real_llm_cutover_runbook.md)。本页说明 Adapter 协议；切换手册说明防污染门禁、Shadow 和回滚。

## 支持模式

- `fixture`：Golden 精确响应；
- `rule_based`：无模型的完整本地演示和确定性回归；它不是正式意图或 QueryPlan 决策引擎；
- `recorded`：回放已脱敏、经审阅的结构化响应；
- `openai_compatible`：内网 Copilot/获准端点。

三个 Node 可共享一个模型，但使用不同 system prompt 和 Pydantic output schema。统一接口只有 `generate()`，operation 只能是五个冻结值；请求没有 Tool、MCP、DB、Gateway、Mapping 或通用 chat escape hatch。

正式职责为：Agent A 决定多轮关系、意图、AnalysisPlan 和显式展示偏好；Agent B 决定逻辑 QueryPlan；Agent C 根据真实查询结果摘要决定洞察和 VisualizationCandidate。Finalizer、DSL Compiler、指标计算、Claim Grounding 和图表可行性校验必须保持确定性。自然语言规则解析只能存在于 `rule_based` Mock Adapter 内，不能成为 `mcp`/生产编排路径。

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
