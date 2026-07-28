# OpenSearch ChatBI POC

可操作的 Mock-first 银行消息数据 ChatBI。用户通过聊天页面提出自然语言问题，
后端完成受控语义解析、跨月 OpenSearch Query DSL、确定性指标计算、Data QA，
并返回 KPI、表格、ECharts 图表、总结和安全清理后的 Evidence。

> 当前所有字段、Mapping、状态码和数据均为 synthetic Mock。项目没有、也不声称
> 已接入银行生产环境。

> **内网 AI/工程师接手：** 不要直接改代码。先完整阅读
> [`INTRANET_START_HERE.md`](INTRANET_START_HERE.md)，按要求提交认知报告，再按
> I0～I6 分阶段接入真实 LLM、真实 `field_catalog_enrich.csv`、多月 Mapping、
> OpenSearch MCP、Metric 和生产 Policy。

内网新 Session 可直接使用：
[`INTRANET_NEW_SESSION_PROMPT.md`](INTRANET_NEW_SESSION_PROMPT.md)。

## 已实现

- `tbl_os_sub_message_YYYY_MM` 跨月索引解析，当前 Mock 包含 2026-06、07、08；
- `record_count.v1` 和 `failure_rate.v1` 确定性计算；
- `status` 的 trim + upper 规范化，未知/空状态进入 `OtherCount`；
- Semantic Compiler、CSV/Mapping 对齐、Import Report、字段检索和 Metric Registry；
- 后端强制 blocked/review-required Policy；
- QueryPlan、OpenSearch DSL Builder、只读校验和字段/索引/桶/时间限制；
- `CountTool`、`SearchIndexTool`、`MsearchTool` 的规则化选择；
- Mock Gateway 和窄接口 `MCPOpenSearchGateway` 内网适配层；
- 真实 LLM 的 provider-neutral `StructuredLLMTransport` 和严格输出校验；
- LLM/Gateway 显式依赖注入，真实模式缺少实现时 fail fast、绝不回退 Mock；
- Data QA、无数据、超时、分片失败、截断和指标对账失败处理；
- 内存 Session、pending clarification、TTL、容量和 reset；
- Jinja2 页面骨架、Vanilla JavaScript 聊天交互、本地 ECharts；
- `/api/chat` 结构化响应和可折叠 Evidence；
- Golden 场景全部通过同一 `/api/chat` 入口。

## 技术选择

```text
Python 3.11+
FastAPI + Pydantic
Jinja2 + HTML + CSS + Vanilla JavaScript
Apache ECharts 6.1.0（本地静态文件）
PyYAML
pytest + Ruff + Pyright
```

本 POC **不使用 LangGraph**。当前流程是单 Agent、有限分支、程序控制的状态机，
LLM 形态适配器只负责 `AnalysisPlan` 和文字总结；Tool 选择、DSL、指标和 QA
都不能由 LLM 自由循环。此结构比引入图编排框架更直接，也保留了以后在流程出现
人工审批、可恢复长任务或复杂并行分支时迁移到 LangGraph 的边界。

明确不包含：

- PPL、PPL fallback；
- Generic OpenSearch API；
- 通用 Tool Registry；
- LLM 自由 Tool loop；
- 多 Agent；
- React/Vue/Streamlit 或 Node 构建链。

## 本地运行

在项目目录执行：

```powershell
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000`。

应用启动时会从 `semantic_sources/` 编译语义模型，并将可审计产物写入
`runtime/`。启动失败代表语义源或指标绑定不合法，不会带病运行。

真实内网模式不是只改环境变量。还必须在内网 bootstrap 中注入真实实现：

```python
create_app(
    settings,
    llm_client=structured_llm_client,
    gateway=mcp_gateway,
)
```

具体方式见：

- [真实 LLM 接入](docs/REAL_LLM_INTEGRATION.md)
- [真实语义资料接入](docs/REAL_SEMANTIC_ONBOARDING.md)
- [真实 OpenSearch MCP 接入](docs/REAL_OPENSEARCH_MCP_INTEGRATION.md)
- [内网分阶段执行清单](docs/INTRANET_EXECUTION_CHECKLIST.md)

## 质量检查

```powershell
python -m pytest -q
python -m ruff check app tests
python -m pyright app tests
node --check app/static/js/app.js
```

## 关键目录

```text
app/
  agent/       # 主流程、状态、AnalysisPlan/QueryPlan/Evidence 契约
  semantic/    # Compiler、Retriever、Resolver、Policy 语义模型
  intent/      # 外网确定性 intent adapter；可替换为结构化输出 LLM
  query/       # 跨月 Index、QueryPlan、DSL、Validator
  gateway/     # Mock、MCP seam、共享 ToolSelector/执行器
  metrics/     # 确定性指标
  results/     # 跨分区合并、图表数据和 Data QA
  sessions/    # 有界内存会话
  api/         # FastAPI 契约和路由
  templates/   # Jinja2 初始页面
  static/      # Vanilla JS、CSS、本地 ECharts
semantic_sources/
mock_data/
scripts/
tests/
docs/
```

## 当前业务基线

- 记录数量等于 OpenSearch document count，不去重；
- 默认时间为 `[2026-07-01T00:00:00+08:00, 2026-08-01T00:00:00+08:00)`；
- 业务时区为 `Asia/Hong_Kong`；
- `failure_rate.v1` 成功状态：`SENT`、`INPROGRESS`；
- `failure_rate.v1` 失败状态：`FAILED`、`ACKFAIL`；
- 分母包含 retry、重复、空状态和未知状态；
- 分母为 0 时 Failure Rate 为 `null`；
- `statusCode` 是 synthetic 运营商原始码，不参与 `failure_rate.v1`。

完整文档入口见 [文档索引](docs/DOCUMENT_INDEX.md)，总体迁移导航见
[内网迁移总指南](docs/INTERNAL_MIGRATION.md)。
