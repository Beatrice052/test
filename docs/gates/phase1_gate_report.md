# Phase 1 Gate Report — Contracts 与 Semantic Compiler

- 日期：2026-08-01
- 结果：**PASSED**
- 基线 SHA-256：`3762adc6ca42745151d01894c835f6d80c9dfb84a6e1ce9624e8b026ed85b6c6`
- Semantic Package：`sp_c882cd989899b08f`

## 1. 本阶段目标

完成 V6.1 严格协议 P1-T01–P1-T09：权威 Pydantic Contract 与 JSON Schema Snapshot、Excel/CSV Adapter、Mapping flatten/diff/hash、注入清洗、Catalog merge、Registry、SQLite FTS5、版本化 Semantic Package 与 Import Report，以及无凭证 Mock 语义输入。

## 2. 主要交付

- `backend/app/contracts/`：39 个权威顶层 Contract，统一 `extra="forbid"`、strict、frozen；覆盖请求、语义、分析、查询、执行、数据集、指标、洞察、Dashboard、Evidence、Session 与错误。
- `docs/schemas/`：39 份确定性 JSON Schema Snapshot；生成和漂移检查脚本位于 `scripts/`。
- `backend/app/semantic/`：Excel/CSV Adapter、Mapping flatten、跨索引能力合并、描述清洗、diff/hash、Semantic Compiler、Package 校验、FTS5 BM25 与 Resolver。
- `backend/app/registries/`：dataset、metric、value、recipe、method、visualization、policy 注册表和公式 AST 白名单校验。
- `semantic-input/mock/`：Mock Excel/CSV、5–7 月 Mapping、注册表与 policy；不含真实凭证或真实业务数据。
- `compiled-semantic/mock/`：可复现 Semantic Package、10 个内容文件 hash、FTS 索引和 PASSED Import Report。
- `fixtures/opensearch/`：mapping conflict 与 ambiguous leaf 失败夹具。

## 3. 关键实现决策

1. Contract 只定义数据；所有跨层对象拒绝额外字段，并通过快照固定兼容面。
2. Compiler 以 Excel/CSV、Mapping、Registry 为 Adapter 输入；运行时只读取编译后的版本化 Package。
3. Mapping 按月合并字段能力，显式区分 `EXACT`、`COERCIBLE`、`PARTIAL`、`CONFLICT`；`.keyword`、nested 和 disabled/object 字段均由确定性规则处理。
4. 外部描述进入检索前清除 prompt-injection 文本；它们始终作为不可信元数据，不能改变系统行为。
5. Metric formula 仅接受白名单 AST，不执行 Python、脚本或任意表达式。
6. Package manifest 对全部 JSON/JSONL 内容计算 SHA-256；加载时强制验证 hash，避免静默篡改。
7. FTS 查询先分词再参数化执行；输入中的引号、运算符或注入语句不能成为 SQLite FTS 控制语法。

## 4. 执行命令

```powershell
cd backend
$env:UV_CACHE_DIR = "$PWD/.cache/uv"
uv run ruff format app tests
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest -q

cd ..
python scripts/check_schema_snapshots.py
uv run --project backend python -m app.cli semantic compile `
  --input-dir semantic-input/mock `
  --output-dir compiled-semantic/mock
```

## 5. 测试实际结果

| 检查 | 结果 |
|---|---:|
| Backend pytest | 99 passed / 0 failed / 0 skipped |
| ruff check | passed |
| ruff format check | passed（54 files） |
| mypy strict | passed（44 source files） |
| 权威 Schema Snapshot | 39 matched / 0 diff |
| Mock semantic compile | exit 0 / PASSED |
| Import Report | 11 catalog rows、15 mapping fields、11 matched、1 mapping-only、1 sanitized、1 blocked |
| Semantic Package integrity | 10 file hashes verified |

测试覆盖：

- 39 个 Contract 的合法最小样例与 extra-field 反例，共 78 个动态契约用例；
- Excel/CSV 等价读取与 prompt-injection 清洗；
- `.keyword` 绑定、nested flatten、object/disabled 处理；
- 5–7 月 `EXACT`、`COERCIBLE`、`PARTIAL` 能力合并；
- duplicate catalog、mapping type conflict、ambiguous leaf、invalid metric 的失败退出与失败 Import Report；
- 两次编译输出完全稳定、manifest/load hash 校验、FTS Top-1 与恶意查询隔离；
- 语义 hash 稳定性和字段 diff；
- 禁止 AgentExecutor/ReAct、禁止用户 raw DSL 的架构扫描。

## 6. Golden 覆盖

本阶段尚未执行需要 Graph/Query/Analytics 的 G01–G25 端到端业务 Golden；已完成它们依赖的 Contract、语义绑定、漂移检测和受控检索底座。Phase 2 起按 Gate 引入会话与 Planner 场景。

## 7. 后续阶段范围

尚未实现而继续留在外网工程范围内：Phase 2–7 的 persistence、StateGraph、三个受限 LLM Node、Query/Gateway、Analytics、Dashboard/Evidence、完整 API/UI、Golden 与发布验收。真实凭证、真实语义输入、真实数据 Shadow 对账及业务口径确认仍是唯一内网输入。

## 8. Gate 判定

| Phase 1 Gate | 证据 | 判定 |
|---|---|---:|
| Mock compile exit 0 | CLI 返回 PASSED，package `sp_c882cd989899b08f` | PASS |
| 注入描述不影响系统 | sanitizer、FTS 恶意查询与文档完整性测试 | PASS |
| `.keyword`、nested、跨月 drift | mapping/unit/integration 测试全部通过 | PASS |
| Schema snapshot 无 diff | 39 authoritative models matched | PASS |

**Phase 1 Gate：PASSED。**

## 9. 下一阶段

进入 Phase 2 Persistence + Graph + Agent A：DB migration、Session/Turn/Answer、identity/ownership、idempotency/lock、单一 StateGraph 空链、Retriever、Fixture LLM、Agent A、AnalysisPlan Validator 与 clarification path。
