# 真实 LLM 切换

## Adapter 边界

Agent A、B、C 只依赖 `StructuredLLMClient.generate(operation, system_prompt, input_payload, output_schema, timeout_seconds, correlation_id)`。当前正式实现为 OpenAI-compatible structured-output Adapter；公司 Copilot 或批准 endpoint 若协议不同，只新增该 Protocol 的 Adapter 和 contract tests，不修改 Agent、Graph 或输出 Contract。

必需 structured-output operations：

- `turn_and_analysis_plan`：Agent A，输出 `AnalysisPlanDraft`。
- `logical_query_plan`：Agent B，输出逻辑 `QueryPlanDraft`。
- `insight_visualization_exploration`：C1，输出统计请求和图表候选。
- `insight_dashboard`：C2，输出 grounded ClaimDraft、KPI selection 与 visual insights。
- `json_repair`：只允许按原 schema 和结构化错误修复，不能改变问题或绕过 Policy。

## 配置与探测

将 Secret 放入内网 Secret 管理，不写 `.env.example`：

```text
APP_ENV=mcp
CHATBI_LLM_MODE=openai_compatible
CHATBI_LLM_BASE_URL=https://approved.example/v1
CHATBI_LLM_MODEL=<approved-deployment>
CHATBI_LLM_API_KEY=<secret injection>
CHATBI_LLM_TIMEOUT_SECONDS=30
```

运行：

```powershell
./scripts/check-real-llm-cutover.ps1 -Output C:\secure\reports\llm-cutover.json
./scripts/probe-llm.ps1 -Output C:\secure\reports\llm-probe.json
```

cutover gate 必须全部通过：正式环境、非 Mock identity/LLM/Gateway/Semantic、Agent 只依赖 Protocol、无 RuleBased import、无 tool parameter、无 raw DSL、operation/schema 独立、超时与 repair 有界。

## Prompt 与数据边界

- Agent A 只看检索候选的 ID、description、semantic type、capability、maturity、compatibility 和安全 cardinality。
- Agent B 只看 `ResolvedAnalysis` 的逻辑描述、Measure AggregationSpec、预算和任务，不看 physical path。
- C1/C2 只看已验证 Dataset schema、最多 500 行受控 payload、完整性、FeatureSummary、Host statistic、Preview 和 material warnings；大表完整内容留在 Evidence artifact。
- 不把完整 Mapping、凭证、endpoint、MCP tool schema、raw document、prompt secret 或未授权字段放入模型上下文。

## Timeout 与 repair

每个调用使用 `CHATBI_LLM_TIMEOUT_SECONDS` 和总轮次超时。Schema 失败只走有限次数的严格 repair；不得解析自由文本、正则提取 JSON、静默切 RuleBased 或扩大字段/工具权限。连续失败应返回受控 limitation/错误并保留审计 correlation ID。

## Shadow 评估

至少按 Agent 分层打分：A 的意图/候选/澄清/required tasks；B 的最小充分 grain、合并/拆分、预算、无 physical path；C1 的统计和 1/N 图动态选择；C2 的任务覆盖、数字 Grounding、限制与图表解释。真实模型质量不以“像 Mock 输出”为目标，禁止把 Mock 关键词逻辑迁入正式模块。
