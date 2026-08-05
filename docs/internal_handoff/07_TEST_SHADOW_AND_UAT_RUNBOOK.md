# 测试、Shadow 与 UAT Runbook

## 环境

- Python 3.12.x、uv、Node 22.17.0、npm；Docker profile 验证需要 Docker。
- 从 clean clone 创建 `.env`，Secret 只由内网系统注入。
- 先使用 Mock package 验证工具链，再使用未提交的真实 semantic input/package。

## 全量本地门禁

```powershell
uv sync --project ./backend --locked
npm.cmd --prefix ./frontend ci
powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/verify-package.ps1
```

分层诊断命令：

```powershell
uv run --project ./backend ruff check ./backend/app ./backend/tests
uv run --project ./backend ruff format --check ./backend/app ./backend/tests
uv run --project ./backend mypy ./backend/app
uv run --project ./backend pytest ./backend/tests -q
npm.cmd --prefix ./frontend run typecheck
npm.cmd --prefix ./frontend run lint
npm.cmd --prefix ./frontend test -- --run
npm.cmd --prefix ./frontend run build
npm.cmd --prefix ./frontend run test:e2e
```

`verify-package` 还会检查 schema/OpenAPI drift、Mock semantic 稳定编译、real-LLM cutover、npm audit、readiness 与浏览器旅程。

## 真实 Golden 格式

每例至少记录：case ID、自然语言问题和多轮上下文、允许 dataset/time/filter、预期 Metric/Measure/Entity/Method、required tasks、可接受 grain/query count、预期数字/容差、图表目的、必须出现的 limitation、raw/source/calculation/claim hashes、Owner 与 verdict。不要只记录最终自然语言答案。

通用性矩阵必须含：

- config-only 新字段、新 numeric measure、新 entity；
- 两套不同 physical names 的 semantic equivalence；
- domain-token guardrail；
- 维度顺序/cardinality、terms/composite 多页、dependent Top-N；
- additive/semi/non-additive rollup；
- raw artifact 对账、metric 重算、stat value path、claim exact binding、used-only definitions；
- QA pass list 不显示、material warning 显示、ERROR/FATAL 阻断；
- 大 artifact preview/download/hash、owner isolation、secret/raw hits 不泄漏、session recovery hash 一致。

## Shadow 执行

1. 运行 cutover、LLM/MCP probe 和只读 smoke。
2. 对每个真实 case 保存 AnalysisPlan、QueryPlan、Compiled DSL、normalized Dataset、Metric result、Dashboard/Evidence。
3. 生成六层 hash 报告：

```powershell
./scripts/build-shadow-report.ps1 --case-id G-REAL-001 `
  --analysis-plan C:\secure\case\analysis-plan.json `
  --query-plan C:\secure\case\query-plan.json `
  --compiled-dsl C:\secure\case\compiled-dsl.json `
  --normalized-dataset C:\secure\case\dataset.json `
  --metric-result C:\secure\case\metric.json `
  --dashboard-evidence C:\secure\case\dashboard-evidence.json `
  --classification DATA_CHANGE --business-verdict NEEDS_REVIEW `
  --output-dir C:\secure\shadow-reports
```

4. MCP Owner 对 raw/source，Metric Owner 对指标/方法，业务 Owner 对任务覆盖和解释，安全 Owner 对权限/脱敏签字。

## UAT Gate

进入 UAT 前：全量自动测试通过；real endpoint probe 通过；全部 REQUIRED input 有 Owner；真实 Golden required tasks 100% 被 grounded claim 或明确 limitation 覆盖；无未分类差异；Evidence 可独立重算；ERROR/FATAL 无肯定结论；跨 tenant/subject 读取为 404/拒绝；rollback 已演练。

结果模板：环境/commit/package version、开始结束时间、命令、passed/failed/skipped、case verdict、差异分类、artifact hashes、Owner、阻断项、批准/拒绝结论。不得声称未运行的 Docker、真实 LLM/MCP 或 UAT 已通过。
