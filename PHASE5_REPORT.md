# Phase 5 验收报告：端到端 ChatBI

**日期：** 2026-07-28

**结果：** 自动化测试通过；浏览器验收结果见最终报告。

**阶段边界：** Agent、Session、多轮、API、结构化页面、本地 ECharts、
Evidence、Golden 和故障流。

## 创建或修改

```text
app/agent/service.py
app/api/routes.py
app/api/schemas.py
app/main.py
app/templates/index.html
app/static/css/app.css
app/static/js/app.js
app/static/vendor/
  echarts.min.js
  ECHARTS-LICENSE.txt
tests/integration/
  test_chat_api.py
  test_health_api.py
  test_home_page.py
  test_golden_scenarios.py
README.md
ARCHITECTURE.md
docs/
  API.md
  MOCK_DATA_DICTIONARY.md
  INTERNAL_MIGRATION.md
  MANUAL_ACCEPTANCE.md
app/intent/structured_client.py
tests/unit/test_structured_llm_client.py
tests/unit/test_dependency_injection.py
INTRANET_START_HERE.md
AGENTS.md
docs/INTRANET_AI_HANDOFF.md
docs/REAL_LLM_INTEGRATION.md
docs/REAL_SEMANTIC_ONBOARDING.md
docs/REAL_OPENSEARCH_MCP_INTEGRATION.md
docs/INTRANET_EXECUTION_CHECKLIST.md
docs/DOCUMENT_INDEX.md
```

## 能力

- 所有回答经同一 `/api/chat` 主链路；
- pending clarification 和最小必要上下文；
- answered/clarification/blocked/not-answerable/error；
- KPI、表格、bar/line chart、指标版本和 warnings；
- Evidence 默认折叠，安全清理后展示；
- blocked 请求在生成 DSL 前停止；
- no data 不生成误导图表；
- Data QA failed 不显示 KPI/table/chart；
- Session reset、TTL、容量和会话内页面恢复；
- ECharts 6.1.0 本地化，无 CDN 和运行时 Node；
- 15 类 Golden/边界场景只调用 `/api/chat`。
- 真实 LLM/Gateway 显式依赖注入边界，缺少实现时 fail fast；
- 真实 LLM Prompt 只含 allowed 字段并经严格 schema 校验；
- 内网 AI 可按背景研读、来源盘点和 I0～I6 Gate 接棒。

## 阶段测试

```text
python -m pytest -q tests/integration
node --check app/static/js/app.js
```

结果：

```text
29 passed
JavaScript syntax: passed
```

最终全量质量门：

```text
108 passed
Ruff passed
Pyright 0 errors / 0 warnings
JavaScript syntax passed
```

## 尚未完成

- 真实 Catalog/Mapping/Policy；
- 真实 MCP 连接与认证；
- 运营商 `statusCode` 规则；
- 生产 RBAC、审计、限流和持久化 Session；
- 真实报表对账。

这些项目必须在内网完成，外网不能猜测。

## 下一阶段

按 `docs/INTERNAL_MIGRATION.md` 执行内网替换与对账，不改 Agent/API/UI 主流程。
