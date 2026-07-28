# API Contract

## `GET /`

返回 Jinja2 初始 ChatBI 页面。业务答案不在 HTML 中硬编码。

## `POST /api/chat`

请求：

```json
{
  "session_id": "session-001",
  "message": "2026年7月各Channel的Failure Rate是多少？"
}
```

- `session_id` 可省略；服务端创建 UUID 会话；
- 允许字符为字母、数字、`-`、`_`；
- `message` trim 后不能为空；
- 当前运行配置最大 2,000 字符。

主要响应：

```json
{
  "session_id": "session-001",
  "run_id": "run-...",
  "status": "answered",
  "assistant_message": "当前口径下总体 Failure Rate 为 33.33%。",
  "needs_clarification": false,
  "clarification_question": null,
  "kpis": [],
  "table": {
    "columns": [],
    "rows": []
  },
  "chart": {
    "type": "bar",
    "title": "Failure Rate by channel",
    "x_field": "channel",
    "y_field": "failure_rate",
    "series_field": null,
    "data": []
  },
  "metric_definition": {
    "metric_id": "failure_rate",
    "metric_version": "failure_rate.v1",
    "status": "POC_DEFINED"
  },
  "warnings": [],
  "evidence": {},
  "reason_code": null
}
```

`status`：

| 值 | 含义 |
|---|---|
| `answered` | 已回答；也用于安全表示 0 行/no data |
| `needs_clarification` | 保存 pending slot，等待下一轮 |
| `blocked` | Policy 后端阻断，未生成 DSL |
| `not_answerable` | 字段、指标、Index 或能力不足 |
| `error` | 执行或 Data QA 失败 |

前端必须按结构渲染，不能解析或执行 `assistant_message` 中的 HTML。

## `POST /api/session/reset`

```json
{"session_id": "session-001"}
```

清空消息、pending clarification、最后计划和 run。

## `GET /api/health`

返回 Mock/Connected 状态、默认时间、Index 范围、语义模型版本和安全能力开关。
不返回 URL、token、密码或真实连接配置。

关键运行状态：

```text
data_source_mode: mock | mcp
connection_status: mock | connected
intent_backend: mock | structured_llm
semantic_model_version: <version>
```

`connected` 只表示应用已注入真实 Gateway；生产 readiness 还必须通过内网 I0～I6
门禁。不得把 health 返回 200 当作报表对账或安全审批已经完成。

## `GET /api/admin/semantic/report`

返回最近一次启动编译的 Import Report。当前 POC 没有身份系统，因此部署到共享
环境前应由反向代理或内网认证限制此管理接口。

## Evidence

Evidence 默认折叠，包含：

- AnalysisPlan；
- 字段选择；
- QueryPlan 和 answerability；
- Tool 和 reason code；
- Query DSL 与 validation checks；
- 原始聚合结果摘要；
- 最终 chart data；
- Data QA。

不包含 document hits、敏感原始值或 blocked 字段。

真实 MCP/LLM 模式还不得包含 endpoint、deployment secret、认证错误正文、provider
原始响应或完整 Prompt。
