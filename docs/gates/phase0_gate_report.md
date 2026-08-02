# Phase 0 Gate Report — 审计与 Greenfield 骨架

- 日期：2026-08-01
- 结果：**PASSED**
- 基线 SHA-256：`3762adc6ca42745151d01894c835f6d80c9dfb84a6e1ce9624e8b026ed85b6c6`

## 1. 本阶段目标

完成 V6.1 严格协议 P0-T01–P0-T06：读取基线、审计现状、建立 Greenfield ADR、新目录/锁文件/CI、创建 `project_memory.md`，并提供无凭证 Mock 前后端一键启动外壳。

本阶段没有进入业务 Contract、Prompt、Query、Gateway、Metric、Dashboard 或 Session 实现。

## 2. 新增/修改文件

主要交付：

- 根目录：`.python-version`、`.nvmrc`、`.node-version`、`.env.example`、`.gitignore`、`README.md`、`Makefile`、`project_memory.md`、`docker-compose.yml`。
- Backend：`pyproject.toml`、真实 `uv.lock`、FastAPI composition root、settings、health API、Dockerfile、3 个测试。
- Frontend：`package.json`、真实 `package-lock.json`、React/Vite Phase 0 shell、严格 TypeScript/ESLint/Vitest 配置、Dockerfile、Nginx 配置、2 个测试。
- 运维：`scripts/dev.ps1`、`scripts/dev.sh`、GitHub Actions CI。
- 文档：Phase 0 audit、ADR-001、本 Gate Report。
- 后续输入目录：`semantic-input/`、`compiled-semantic/`、`fixtures/opensearch/`、`evals/golden/`。

排除 `.venv`、`node_modules`、`.cache`、lint/test cache、`dist` 和 TypeScript build metadata 后，本阶段交付文件共 49 个；生成物不作为功能完成证据。

## 3. 关键架构决策

1. 全新 `opensearch-chatbi-v6/` 目录，不复制旧核心代码。
2. 一个 FastAPI composition root；后续一个 StateGraph 与三个 LLM Node 只能从该 root 装配。
3. Mock profile 默认 `fixture LLM + mock gateway`，不读取 API Key 或 OpenSearch 凭证。
4. Python 严格约束 `>=3.12,<3.13`；Node 严格约束 `>=22,<23`。
5. 前端采用安全声明式 React shell；不含指标公式、DSL、MCP 或 raw ECharts option。
6. ECharts 直接锁定到修复已知 XSS 的 6.1.0 以上版本；npm audit 必须为 0。
7. 开发宿主 Vite/Vitest 使用 `configLoader runner`，避免 config bundle 在受限 Windows 文件系统向上扫描。

## 4. 执行的命令

Backend：

```text
python -m pip install "uv>=0.7,<1"
uv lock --python <managed-cpython-3.12>
uv sync --all-groups --python <managed-cpython-3.12>
uv sync --all-groups --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest -q
```

Frontend：

```text
npm install
npm ci
npm run lint
npm run typecheck
npm run test -- --run
npm run build
npm audit --json
```

额外验证：

```text
PowerShell AST parse scripts/dev.ps1
sh -n scripts/dev.sh（宿主无 sh，未执行）
PyYAML parse docker-compose.yml + service assertion
rg forbidden pattern audit（生成依赖与文档排除后检查代码/配置）
```

## 5. 测试实际结果

| 层 | 结果 |
|---|---:|
| Backend pytest | 3 passed / 0 failed / 0 skipped |
| Frontend Vitest | 2 passed / 0 failed / 0 skipped |
| Backend ruff check | passed |
| Backend ruff format check | passed |
| Backend mypy strict | passed，6 个 app source files 无问题 |
| Frontend ESLint | passed，0 warnings |
| Frontend TypeScript strict | passed |
| Frontend production build | passed，29 modules transformed |
| npm audit | 0 vulnerabilities |
| PowerShell script parse | 0 errors |
| Compose YAML structure | passed，恰含 backend/frontend 两个 Mock profile service |

网络启动证据：

- `test_uvicorn_serves_mock_readiness_over_http` 使用真实 TCP listener 启动 Uvicorn，GET `/api/v1/health/ready` 返回 200、`status=ready`、`profile=mock`，随后干净退出。
- `dev-server.test.ts` 使用真实 TCP listener 启动 Vite，GET `/` 返回 200 并包含应用标题，随后关闭 server。

## 6. 覆盖的 Golden

本阶段不声明 G01–G25 业务 Golden 覆盖；这些需要 Phase 1–7 的 Contract 和业务链。Phase 0 仅覆盖无凭证 Mock 启动、锁文件可复现和进程入口。

## 7. 未完成项

按阶段计划尚未开始、而非遗留核心 TODO：

- Phase 1–7 的 Contracts、Semantic、Graph、Query、Gateway、Analytics、Dashboard、Evidence、Session、完整 API/UI 与 G01–G25。
- 宿主未安装 Docker，未在本机执行容器 build/run；Compose 已静态校验，CI/具备 Docker 的环境仍需执行 profile 验证。
- 宿主无 POSIX `sh`，未执行 `sh -n`；脚本使用 POSIX `sh` 语法并将在 Linux CI/容器环境验证。

没有把上述通用实现事项留给内网；它们全部保留在外网后续 Phase 范围内。

## 8. Gate 判定

| Phase 0 Gate | 证据 | 判定 |
|---|---|---:|
| 新旧路径清楚 | 审计确认无旧仓库；新目录独立 | PASS |
| 无核心代码从旧系统复制 | 工作区无旧代码；ADR-001 Greenfield | PASS |
| Backend/Frontend 空骨架可启动 | Uvicorn/Vite 真实 TCP/HTTP 测试 | PASS |
| 用户确认审计 | 续作目标明确要求按确认后 Phase 0–8 执行 | PASS |
| 锁文件与 CI | `uv.lock`、`package-lock.json`、CI workflow | PASS |
| Mock 一键启动壳 | PowerShell/Linux 脚本 + Compose Mock profile | PASS |

**Phase 0 Gate：PASSED。**

## 9. 下一阶段计划

进入 Phase 1 Contracts + Semantic：先定义全部权威 Pydantic Contract 和 JSON Schema Snapshot，再实现 Excel/CSV Adapter、Mapping flatten、Sanitizer、Catalog merge、Registry、FTS5、Semantic Package/Import Report 与 Mock semantic files。Phase 1 Gate 未通过前不进入 Persistence/Graph。
