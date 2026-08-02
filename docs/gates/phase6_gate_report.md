# Phase 6 Gate Report — API 与 React Session Workspace

- 日期：2026-08-01
- 结果：**PASSED**
- 唯一基线 SHA-256：`3762adc6ca42745151d01894c835f6d80c9dfb84a6e1ce9624e8b026ed85b6c6`
- Semantic Package：`sp_c882cd989899b08f`

## 1. 本阶段交付

- FastAPI 提供 Session 创建、列表、读取、重命名、归档，Chat、Turn cancel，Answer、Evidence、Dataset rows/CSV、Semantic current/compile/report 等完整工作区 API。
- 所有业务对象读取均以认证 subject 作为 Repository 查询条件；不存在“先按 ID 读取、再做所有权判断”的旁路。
- `mock`/`local-os` 开发 profile 使用固定 Mock Identity；外部 `mcp`/生产接入只接受上游可信身份头，且 Advanced Evidence 需要显式角色。生产环境会硬拒绝 Mock Identity。
- 同一 `client_turn_id` 通过持久化幂等记录返回原 AnswerSnapshot；Session 版本、锁、归档和 cancel 边界均返回稳定 API 错误。
- OpenAPI 文档由后端实际路由生成；前端 48 个 TypeScript 类型和 client 路径由该文档生成，避免手工复制 Contract。
- React Session Workspace 包含 Session Sidebar、Chat/Answer Timeline、动态 Dashboard Grid、Dataset Table、Evidence Drawer、CSV 下载、loading/error/cancel、刷新与切换恢复。
- `SafeChart` 只从受控 `ChartSpec` 构造 ECharts option；前端不接收 raw option、formatter function、`renderItem`、HTML 或任意 JavaScript。
- Dashboard 中所有业务数字均来自后端 Dataset/Metric，前端不实现 failure rate 或其他业务指标公式。
- CSV 导出由后端 Evidence exporter 生成，防止 `= + - @` 公式注入。

### Dashboard 交互校准（2026-08-01）

Dashboard 页面现在按后端声明式 Block 动态呈现：去重后的总分析 → 本轮 AnalysisPlan 选择的 KPI → 多图 Dashboard（每图含“如何阅读”）→ 分析边界 → 后续追问。图表数量、图型、维度、系列和标题均取决于当前 AnswerSnapshot，不由前端固定为某个业务组合。技术聚合明细、指标口径与完整 DataQA 只在证据抽屉展示；显式表格请求仍呈现业务结果表。

证据抽屉按用户检查路径重构为：OpenSearch 检索聚合表 → 指标计算（结果、分子、分母、排除项、定义）→ 质量与对账；高级证据单独展示只读 DSL 和执行摘要。正常 Dashboard 不再重复摆放验证明细，无可行图或用户明确要求表格时才在主回答降级展示表格。

## 2. Gate 证据

- Playwright G02：新建 Session 后执行 7 月 Channel 综合分析，KPI、图表、表格与 Evidence 能完整展示。
- Playwright G15：同一 Answer 的多个展示块复用后端 Dataset；页面不触发按图查询。
- Playwright G25：刷新后从持久化 Session/Turn/AnswerSnapshot 恢复；切换 Session 不混淆历史状态。
- 新建 Session 后无上一个 Session 的 active analytical context；API 集成测试覆盖该隔离边界。
- 前端安全测试递归检查 chart payload 和 DOM，阻止 raw option、HTML 注入与客户端指标公式。
- Business Evidence 不返回 DSL；Advanced Evidence 在授权角色下返回审计快照；Debug API 默认关闭。

## 3. 实际验证结果

| 检查 | 结果 |
|---|---:|
| Backend pytest（Phase 6 检查点） | 164 passed / 0 failed / 0 skipped |
| Frontend Vitest | 5 passed / 0 failed |
| Playwright G02/G15/G25 合并旅程 | 1 passed / 0 failed |
| Frontend typecheck | passed |
| Frontend ESLint | passed |
| Frontend production build | passed |
| Backend ruff check/format | passed |
| Backend mypy | passed（119 source files） |
| 权威 Schema Snapshot | 39 matched / 0 diff |

## 4. Gate 判定

| Phase 6 Gate | 证据 | 判定 |
|---|---|---:|
| Playwright G02/G15/G25 | 完整 Session→Chat→Dashboard→Evidence→恢复旅程 | PASS |
| 刷新与切换恢复 | AnswerSnapshot API + Query cache 恢复断言 | PASS |
| 新 Session 不继承 | subject/session context 隔离测试 | PASS |
| 前端无指标公式 | 业务数字仅消费 Dataset/Metric API | PASS |
| 无 XSS/raw HTML | SafeChart allowlist + 安全测试 + 无 HTML escape hatch | PASS |

**Phase 6 Gate：PASSED。**

## 5. 下一阶段

进入 Phase 7：G01–G25 全层 Golden、Docker profiles、Linux/PowerShell 验包脚本、OpenAI-compatible LLM/MCP/Schema 接入指南、内网 Checklist、Test Report、ADR 汇总与 `project_memory.md` 更新。
