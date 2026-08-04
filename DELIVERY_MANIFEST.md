# MI-NEW 交付清单

生成日期：2026-08-04

目标仓库：Beatrice052/test

目标分支：MI-NEW（orphan/new branch）

## 权威基线

- 仓库内路径：docs/baseline/OpenSearch_ChatBI_V6.1_Master_Execution_Spec_含_opensearch-agent_架构校准.md
- SHA-256：3762ADC6CA42745151D01894C835F6D80C9DFB84A6E1CE9624E8B026ED85B6C6
- 原文件与仓库副本逐字节 hash 一致。

## 交付入口

内网 AI 必须按以下顺序：

1. AGENTS.md
2. docs/integration/INTERNAL_AI_START_HERE.md
3. docs/requirements_traceability.md
4. docs/integration/real_llm_cutover_runbook.md
5. docs/integration/multi_agent_orchestration.md
6. docs/integration/mcp_adapter_guide.md
7. docs/integration/visualization_agent_architecture.md
8. docs/internal_checklist.md

`docs/gates/` 和早期 phase 审计只保留为历史证据，不能作为当前实现说明；其中旧的单阶段 Agent C 描述已被上述入口文档取代。

## 包含内容

- backend：FastAPI、确定性 LangGraph 主编排器、三个有界 Agents、字段语义 Descriptor、Query、MCP index/mapping/profile Gateway、Analytics、Agent C 双阶段 Visualization Explorer、Presentation、Persistence、Security、CLI、Alembic；
- frontend：React/TypeScript/Vite/ECharts 安全工作区、Session、Dashboard、Evidence、SSE；
- semantic-input/mock：可运行 Mock 输入；
- semantic-input/internal-template：真实输入模板，不含真实业务数据；
- compiled-semantic/mock：已签入可运行 Mock Semantic Package；
- fixtures/evals：Mock fixtures 和 G01–G25；
- scripts：Windows/Linux verify、probe、snapshot、prepare、compile、configure、smoke、shadow；
- docker/Compose：mock、local-os、mcp profiles；
- docs：唯一基线、ADR、Gate、接入、审计、测试、追踪和 Checklist；
- CI：Python 3.12、Node 22.17.0、后端、前端、E2E、npm 高危 audit。

## 不包含内容

- .env 或任何真实 Secret/Key/证书；
- 真实字段 Excel/CSV、真实 Mapping/Profile Snapshot、真实索引数据；
- semantic-input/internal、evals/golden/internal、reports/internal；
- 运行数据库、artifact、日志、缓存、虚拟环境、node_modules、dist；
- 真实 LLM/MCP probe 结果或业务 Shadow 明文。

## 最终本地门禁事实

| 项目 | 结果 |
|---|---|
| Backend pytest | 275 passed |
| Ruff / format | passed |
| mypy | 130 sources passed |
| Schema snapshots | 41 matched |
| OpenAPI/TS | 55 matched |
| Frontend tests | 19 passed |
| Production build | passed |
| Chromium E2E | 1 passed |
| Semantic repeatability | 12 files, identical hashes |
| Mock semantic version | sp_d59d2225dd6b8317 |
| Real cutover static gate | 12/12 passed |

边界：当前主机 Node 24.14.1、无 Docker、npm audit endpoint 被网络 sandbox 阻断；完整 Node 22/Docker/audit 和所有真实接入项由 CI/内网按手册执行。本交付不虚报真实 LLM/MCP/业务 Shadow。

## 分支完整性验证

克隆后运行：

~~~bash
git checkout MI-NEW
git status --short
git rev-parse HEAD
git log -1 --oneline
~~~

该分支是独立 orphan 交付分支，不继承目标仓库 main 的业务文件。工作区应干净。然后运行 scripts/verify-package.ps1 或 scripts/verify-package.sh。
