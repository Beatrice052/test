# Phase 2 Gate Report — Persistence + Graph + Agent A

- 日期：2026-08-01
- 结果：**PASSED**
- 基线 SHA-256：`3762adc6ca42745151d01894c835f6d80c9dfb84a6e1ce9624e8b026ed85b6c6`
- Semantic Package：`sp_c882cd989899b08f`

## 1. 本阶段目标

完成 V6.1 严格协议 Phase 2：SQLite migration、Session/Turn/Answer persistence、identity/ownership、`client_turn_id` 幂等、Session lease lock、单一 low-level LangGraph StateGraph、SQLite Checkpointer、Semantic Retriever、Fixture/Rule-based Mock LLM、DataAnalystPlannerAgent、AnalysisPlan Validator、字段/指标 Resolver、Answerability 与 clarification path。

## 2. 主要交付

- `backend/migrations/`、`backend/alembic.ini`：首个可执行 Alembic migration，创建规范列出的 10 张 POC 表。
- `backend/app/persistence/`：Database、Session/Turn、AnswerSnapshot、Idempotency、Session Lock 与 UUIDv7-style ID；所有对象读取在 SQL 内包含 `subject_id`。
- `backend/app/security/`：Mock identity、受信任身份头 Adapter 与 role gate；对象所有权仍由 Repository 强制执行。
- `backend/app/llm/`：无 Tool 参数的 `StructuredLLMClient`、Fixture LLM、Rule-based Mock LLM、最小化定向修复与 Secret redaction。
- `backend/app/agents/analyst_planner.py`：Agent A 只接收最小候选摘要，不读取 Mapping、数据库、MCP、凭证、raw data 或 DSL。
- `backend/app/orchestration/`：唯一 StateGraph、明确节点/条件边、Context/Turn Router、候选 allowlist Validator、两次修复上限、安全 fallback、Orchestrator 与 checkpoint recovery。
- `backend/app/semantic/resolver.py`：字段、指标、值字典和 policy 的确定性解析，输出 `ResolvedAnalysis`。
- `fixtures/llm/analysis_plans.json`：无凭证严格 Fixture。
- composition root、Windows/POSIX 启动脚本、Docker build context 与 CI 已接入 migration、Mock compile 和 checkpoint。
- Windows 补充锁定 `tzdata`，确保 `Asia/Hong_Kong` 在各平台一致可用。

## 3. 关键实现决策

1. `subject_id` 不是 API 层事后校验；Session、Turn、Answer、Idempotency 和 Lock 的 Repository SQL 都把所有权作为查询条件。
2. 幂等 key 在同一 subject/session 唯一；同 payload 的 RUNNING/COMPLETED 分别返回原 Turn/Answer，不同 payload 使用同 key 直接冲突，retryable failure 创建新 attempt。
3. Answer、Turn 完成、Idempotency 完成和 Session active context 在一个事务内原子提交；只有该事务成功才返回完成状态。
4. 同一 Session 使用排他 lease lock，支持 heartbeat、owner-only release 和过期锁回收；不同 Session 不共享锁。
5. Graph State 是结构化业务对象，不是 messages 数组；System Prompt、凭证、完整 Mapping 和 Tool list 不进入 checkpoint。
6. 每次 Agent A 前，LangGraph 和 Turn safe-state 均已有候选 ID/checkpoint；进程重启后用原 `thread_id` 恢复，不重复调用 Agent A。
7. Agent A 输出仍是 Draft；程序强制 Candidate ID allowlist、Turn relation 和 Answerability。最多两次 `json_repair`，且修复输入只含原输出、错误码、允许 ID、问题 hash 和 attempt。
8. 两次修复仍不合法时生成确定性 clarification，不执行臆造字段、指标或数据集。
9. 中文 FTS 增加确定性 CJK n-gram 索引，并在字段/指标命中但数据集未命中时提供受 policy/allowlist 约束的数据集候选兜底。

## 4. 执行命令

```powershell
cd backend
$env:UV_CACHE_DIR = "$PWD/.cache/uv"
uv lock
uv sync --all-groups --locked
uv run ruff check app tests migrations
uv run ruff format --check app tests migrations
uv run mypy app
uv run pytest -q

cd ..
python scripts/check_schema_snapshots.py
uv run --project backend python -m app.cli semantic compile `
  --input-dir semantic-input/mock `
  --output-dir compiled-semantic/mock
```

另外执行了 PowerShell AST parse、Compose YAML/build-context 断言、真实 Uvicorn TCP/HTTP readiness 测试，以及 Alembic upgrade integration test。

## 5. 测试实际结果

| 检查 | 结果 |
|---|---:|
| Backend pytest | 118 passed / 0 failed / 0 skipped |
| ruff check | passed |
| ruff format check | passed（95 files） |
| mypy strict | passed（74 source files） |
| 权威 Schema Snapshot | 39 matched / 0 diff |
| Mock semantic compile | exit 0 / PASSED / `sp_c882cd989899b08f` |
| Alembic initial migration | 10 required tables created |
| Phase 2 targeted suite | ownership、idempotency、locks、recovery、Agent、Graph、clarification 全通过 |
| PowerShell AST / Compose structure | passed |

关键行为证据：

- 新 Session 和 `NEW_TOPIC` 不继承旧 filter；显式 FILTER/TIME follow-up 只继承当前 Session 的 active context；
- AnalysisPlan 中 dataset、metric、field、method 引用全部来自候选 allowlist；invented ID 被拒绝；
- 无效 Draft 只进行两次定向修复，第三次转安全 clarification；
- 关闭并重新打开业务 SQLite 与 checkpoint SQLite 后，原 pending Turn 沿原 thread 恢复，Agent A 调用次数为 0；
- 文件型数据库重启后可读取 RUNNING 与 retryable FAILED 的 request 和安全状态；
- COMPLETED `client_turn_id` 重放返回原 AnswerSnapshot，不再次调用 LLM；
- 另一 subject 查询 Session/Answer/Turn 返回 owned-object not found；
- Agent 源码无 Gateway、MCP、DB import，LLM 接口无 `tool/tools/tool_choice` 参数；
- Agent checkpoint 不含 System Prompt 或 OpenSearch Secret 名称。

## 6. Golden 覆盖

本阶段完成 G17 的 Session 继承边界、G23 的幂等重放、G24 的所有权隔离，以及 G22 所需的候选清洗/allowlist/无 Tool 防线。G25 已覆盖 pending/failed 与 checkpoint 恢复底座；包含 Dashboard/Dataset/Evidence 的完整历史快照须在 Phase 5–6 对象落地后做端到端断言。G01–G12 的 Query/Dataset/Metric 最终断言从 Phase 3–5 逐步完成。

## 7. 后续阶段范围

尚未实现而继续留在外网工程范围内：Phase 3 的 Agent B、QueryPlan/DSL/Gateway；Phase 4 的 Result/Metric/Statistic/QA；Phase 5 的 Agent C、Dashboard/Evidence；Phase 6 的完整 API/UI；Phase 7 的 Golden、故障、性能、安全与发布验收。没有把这些核心任务转交内网。

内网仍只需提供真实 Excel/Mapping、真实 MCP/LLM 配置与凭证、failure_rate 业务口径确认及真实数据 Shadow 对账。

## 8. Gate 判定

| Phase 2 Gate | 证据 | 判定 |
|---|---|---:|
| 新问题/追问/新 Session 不错继承 | Context Router 与 active-context tests | PASS |
| AnalysisPlan 只引用候选 ID | allowlist positive/negative tests | PASS |
| 进程重启可恢复 pending/failed state | 双 SQLite close/reopen、checkpoint resume、RUNNING/FAILED recovery tests | PASS |
| 无 OpenSearch Tool 绑定给 Agent | AST dependency guard + LLM interface guard | PASS |

**Phase 2 Gate：PASSED。**

## 9. 下一阶段

进入 Phase 3 Agent B + Query + Gateway：LogicalQueryPlannerAgent、QueryPlan Finalizer、Index Router、AST/Compiler/Validator、Mock Gateway、MCP Adapter/Probe、terms/composite/dependent query 与 fault injection。
