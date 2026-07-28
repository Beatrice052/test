# Phase 1 验收报告

**日期：** 2026-07-28

**结果：** 通过

**阶段边界：** 项目骨架、契约、配置、Session、页面外壳与基础 API；未开始语义编译或查询。

## 本阶段创建的文件

```text
pyproject.toml
.env.example
.gitignore
README.md
ARCHITECTURE.md
PHASE1_REPORT.md
app/
  __init__.py
  main.py
  agent/
    __init__.py
    contracts.py
    state.py
  api/
    __init__.py
    errors.py
    routes.py
    schemas.py
  config/
    __init__.py
    settings.py
  sessions/
    __init__.py
    models.py
    store.py
  templates/
    index.html
  static/
    css/app.css
    js/app.js
    vendor/README.md
tests/
  conftest.py
  unit/
    test_contracts.py
    test_settings.py
    test_session_store.py
  integration/
    test_health_api.py
    test_home_page.py
```

## 已实现能力

- FastAPI 应用工厂与一条命令启动；
- Jinja2 首页骨架和本地 CSS/JavaScript；
- 页面显示 Mock OpenSearch、`tbl_os_sub_message_YYYY_MM`、默认时间、时区和模型状态；
- 示例问题、多行输入、Enter/Shift+Enter、loading、防重复提交、Clear Conversation；
- AnalysisPlan、QueryPlan、Evidence、Chat request/response 等严格 Pydantic 契约；
- AnalysisPlan 和 QueryPlan 禁止附带 Tool 或 DSL；
- 显式有限 Agent 状态和合法转移校验；
- 所有时间与月份 Index 规则集中配置；
- 有 TTL、容量、消息上限和 LRU 淘汰的线程安全内存 Session Store；
- pending clarification 数据结构；
- `GET /`、`GET /api/health`、`POST /api/session/reset`；
- `POST /api/chat` 的最终结构契约；当前明确返回 HTTP 501 和
  `PHASE_NOT_IMPLEMENTED`，没有硬编码业务结果；
- 首页与 API 不加载 CDN 或外部服务。

## 执行的测试

```text
python -m pytest -q
python -m ruff check .
python -m pyright app tests
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

结果：

```text
29 passed
ruff: All checks passed
pyright: 0 errors, 0 warnings
```

## 浏览器验收

- 首页成功加载，Mock 标识可见；
- Index 范围显示为 `tbl_os_sub_message_YYYY_MM`，没有误写为只查 7 月；
- 默认时间显示为 2026 年 7 月完整月份，时区为 `Asia/Hong_Kong`；
- 示例问题可填入输入框；
- Enter 可提交，请求期间按钮防重复提交；
- Phase 1 的 chat 返回明确阶段提示，不生成业务结果；
- Clear Conversation 清空当前页面及服务端 Session；
- 1440×900 桌面视口无页面级横向溢出；
- 无外部 script/stylesheet，浏览器控制台无 error/warning。

## 尚未完成

- synthetic Field Catalog、Mock Mapping 和多月份 Mock 数据；
- Semantic Compiler、Import Report、Policy Engine；
- Mock Intent Parser、字段检索、Metric Resolver、Answerability；
- Monthly Index Resolver、QueryPlan Builder、DSL Builder、Validator；
- OpenSearch Gateway、Tool 选择和 Mock Executor；
- 完整 ChatBIAgent 主链和澄清续答；
- `failure_rate.v1`、运营商 `status_code` 解析、Data QA；
- KPI、表格、ECharts、完整 Evidence 渲染；
- G01～G27。

## 下一阶段

Phase 2 仅实现 synthetic Catalog/Mapping、Semantic Compiler 和 Mock Policy，
并以 `candidate_role` 隔离、Mapping 对齐、blocked/review-required 字段和
Import Report 为阶段闸门。开始前等待用户确认。
