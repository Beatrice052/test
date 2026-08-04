# ADR-002：Adapter 与安全边界

- 状态：Accepted
- 日期：2026-08-01

## 决策

- 三个 LLM Node 只依赖 `StructuredLLMClient.generate()`；Agent C 使用两个有界结构化 operation，全部 operation 由 `ALLOWED_OPERATIONS` 冻结；接口无 `tools`、MCP、DB、Gateway 或通用 `chat()`。
- OpenAI-compatible adapter 只调用受配 endpoint 的 `/chat/completions`，使用 Pydantic JSON Schema strict response format；响应未通过严格 Contract 即失败，不降级为自由文本解析。
- OpenSearch 默认真实路径是官方 MCP Python SDK transport + `McpOpenSearchGateway`；Tool discovery 仅启动/probe 使用。
- Bootstrap/Refresh 可通过独立 `SemanticMetadataGateway` 调用 list indices、mapping 和固定 `size:0` field profile；先由 staging Semantic Package 应用 Policy，再画像 model-visible/aggregatable 字段。该管理接口不注入 Agent，也不在普通问答时调用。
- required Tool 只有 list indices、mapping、search、health；Generic API、PPL、Memory、Agentic 和写 Tool 不绑定。
- endpoint/key/password/token/cert 只来自环境变量或 Secret Store，不进入 Plan、DSL、Evidence、日志或报告。
- `direct` Gateway 不是当前可用 fallback；若未来批准，必须新增 ADR、实现同一 `OpenSearchGateway` Contract 并通过全部安全/Golden 测试。

## 后果

内网替换 endpoint/model/Secret/MCP transport 不改变 Agent、Graph、Contract、Compiler 或 Analytics。Agent A/B 只消费编译后的安全 description/能力/兼容性/基数摘要，不消费 physical path 或 raw documents。端点不支持 strict structured output 或 MCP Tool schema 不兼容时，probe 明确失败，不能静默绕过治理。
