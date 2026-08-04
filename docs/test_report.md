# OpenSearch ChatBI V6.1 最终测试报告

日期：2026-08-04

结论：外网工程与 Mock 运行 READY_FOR_INTERNAL_SHADOW

## 1. 最终结果

| 门禁 | 结果 |
|---|---|
| Ruff lint | PASS |
| Ruff format | PASS |
| mypy strict | PASS，130 source files |
| Backend pytest | PASS，275 tests |
| G01–G25 | PASS，包含在后端全量 |
| JSON Schema snapshots | PASS，41 models |
| OpenAPI/TypeScript schemas | PASS，55 schemas |
| Frontend ESLint | PASS |
| Frontend TypeScript | PASS |
| Frontend Vitest | PASS，7 files / 19 tests |
| Vite production build | PASS |
| Chromium Playwright | PASS，1 end-to-end journey |
| Semantic compile repeatability | PASS，12 files 内容 hash 完全一致 |
| Mock package version | sp_d59d2225dd6b8317 |
| Real LLM cutover static gate | PASS，12/12 |

后端全量命令在 backend 目录执行，结果为 275 passed、0 failed、0 skipped。pytest 不再依赖仓库内固定 basetemp/cache，避免 Windows 并发或残留句柄造成 setup 级假失败。

## 2. 重点业务流程覆盖

- 新问题：Agent A → Resolver → Agent B → Compiler → Gateway → Analytics/QA → Agent C Pass 1 → Visualization Explorer → Agent C Pass 2 → Grounding → Dashboard/Evidence。
- 纯换图/解释：数据签名不变时复用、零 Gateway。
- 混合“实质新问题 + 图表要求”：不会误复用；强制新查询。
- 时间、过滤、维度、grain、指标变化：数据签名变化即 requery。
- 单值、排名、趋势、二维、构成、Pareto、异常、明细、空结果、高基数。
- 用户显式 line、heatmap、table；兼容采用，不兼容安全降级。
- KPI 数量和图表数量动态；普通问题不固定四卡/四图。
- required task 对应 Grounded Claim 或 limitation；Agent C 有界 repair。
- Preview 与 Claim 的 task/Dataset/measure/Evidence 一致；错指标结论不能挂到图上。
- 同 Dataset/同 intent 的不同受治理 measure 不会被错误去重。
- 主页面总分析优先；技术聚合、指标口径、QA 进入 Evidence。
- OpenSearch 原始聚合表、指标公式/分子/分母/排除项、QA、授权 DSL 可追溯。

## 3. Query、Analytics 与数据质量覆盖

- AnalysisPlan/ResolvedAnalysis/QueryPlan/CompiledQuery/DatasetBundle 分层。
- Agent A 候选与 Agent B `ResolvedFieldDescriptor` 含 description/semantic type/capability/compatibility/cardinality，且不含 physical path。
- MCP Adapter 覆盖受控 index discovery、Mapping 与 `size:0` FieldProfile；Compiler 拒绝 profile/mapping hash 或 index 不一致。
- Agent B 无 DSL；Compiler 使用白名单 AST 和确定性 index/time/filter/agg。
- Finalizer 强制 required task 的 metric/dimension/grain 最小充分覆盖；预算内自动提升 bucket 低估，高基数超预算在 DSL 前拒绝。
- Query consolidation 防止一图一查；同一二维 Dataset 支撑多种展示。
- Composite 多页限制与完整性；后续页 shard failure 会产生 fatal QA。
- Gateway timeout/retry/size/cancel；总轮次 TURN_TIMEOUT 是 retryable FAILED。
- 递归 Bucket normalization、稳定 row_id、grain/column/completeness。
- message_record_count、failure_rate 的受治理公式和质量。
- 率指标 numerator、denominator、excluded、minimum denominator。
- total/subtotal、范围、分母、时区、Mapping、空/部分结果对账。

## 4. 会话、安全和恢复覆盖

- subject-scoped Session/Answer/Dataset/Evidence。
- 跨 subject 访问隔离。
- client_turn_id 幂等，执行中去重，失败可重试。
- lock heartbeat、取消、checkpoint、进程恢复和不可变历史。
- raw DSL、写/删请求、Prompt/metadata injection 零查询拒绝。
- Mock Identity/LLM/Semantic 在 mcp/prod/production fail closed。
- Advanced Evidence ACL、CSV formula injection、前端 XSS/raw HTML/JS 边界。
- SafeAuditLogger 仅记录 allowlisted 元数据，不记录 Prompt、数据行、DSL、endpoint 或 Secret。

## 5. 前端与流式覆盖

- Session 新建、切换、归档、刷新恢复。
- 实际 LangGraph 节点 SSE 进度，不显示隐藏推理。
- 最终 AnswerSnapshot 到达后进度自动收起。
- Answer-first Dashboard、动态 KPI、每图 purpose/findings/reading guide/caveat 和追问。
- 技术 QA/“聚合明细与指标口径”不在主页面。
- Evidence Drawer 的业务层和授权高级层。
- SafeChart 仅从声明式字段构造安全 option。
- Chromium E2E 覆盖 G02/G15/G25：会话隔离、恢复和证据支持。

## 6. 重复语义编译

同一个 semantic-input/mock 编译到两个独立目录：

~~~text
package_version = sp_d59d2225dd6b8317
field_count = 12
artifact_file_count = 12
file_names = identical
sha256_per_file = identical
~~~

Compiler 的 FTS、manifest、Import Report 和内容产物可重复。

## 7. 正式 LLM 切换门禁

使用无真实 Secret 的合规形式配置执行静态 cutover，以下 12 项全部通过：

1. live_environment
2. live_llm_adapter
3. llm_endpoint_configured
4. llm_model_configured
5. trusted_identity
6. mcp_gateway
7. non_mock_semantic_package
8. non_mock_semantic_input
9. mock_adapter_isolation
10. no_formal_text_intent_parser
11. three_live_agent_operations
12. compiler_owns_dsl

该结果只证明代码边界和配置形态正确；真实 endpoint 仍须 probe-llm 和 Shadow。

## 8. 当前主机未执行项

- 当前 Node.js 为 24.14.1；发布锁定版本是 22.17.0。分层 lint/type/unit/build/E2E 全部通过，GitHub CI 固定 22.17.0，完整 verify-package 在 Node 22 主机重跑。
- 当前主机没有 Docker，因此未执行真实 Docker image build/profile run；Compose 与 profile 由 YAML/架构测试验证。
- npm audit 因网络 sandbox 无法访问 npm registry audit endpoint，不能声称本机审计通过；CI 已增加 npm audit --audit-level=high。
- 无真实 LLM/MCP/Excel/Mapping/Secret/业务口径，因此不声称真实 probe、真实指标对账或生产 Shadow 通过。

## 9. 非阻塞 warning

- Starlette TestClient 有一条上游 deprecation warning。
- Vite 对 ECharts 主 chunk 报大于 500 kB warning；production build 和 E2E 成功，功能与安全不受影响。

## 10. 上线前必须补齐

按照 docs/integration/INTERNAL_AI_START_HERE.md 完成 Node 22/Docker 门禁、真实 Semantic、12/12 cutover、LLM/MCP probe、只读 smoke、G01–G25 真实 Shadow、指标重算、Evidence ACL、Ingress SSE 和业务 Owner verdict。
