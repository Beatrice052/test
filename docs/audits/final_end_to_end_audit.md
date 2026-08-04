# 最终端到端审计

审计日期：2026-08-04

审计结论：READY_FOR_INTERNAL_SHADOW

适用范围：本仓库 Mock-first 外网交付，不包含真实 LLM/MCP/业务数据 verdict

## 1. 总体判断

该项目已经从“固定示例输出”校准为受治理、Adapter-based 的通用 ChatBI 框架。用户问题不会被硬编码为 Channel×Status×Month；正式意图、AnalysisPlan、QueryPlan 和查询后分析分别由真实 Agent A/B/C 决定。Agent C 当前采用“探索请求 → 受控 Preview → Claim/VisualInsight 同时绑定”的双阶段，确定性组件负责 ID/预算/DSL/指标/QA/Grounding/图表安全。

本轮没有只修单个截图。审计从用户输入、语义检索、三个 Agent、Query/DSL、Gateway、Analytics、Dashboard、Evidence、SSE、会话、安全、恢复、部署和内网切换逐层检查，并补充了跨层回归。

在没有真实凭证和真实业务输入的外网环境下，结论是“可以交给内网进入受控接入与 Shadow”，不是“已经完成真实生产上线”。

## 2. 问题 framing 与方法

审计回答的不是“当前 Mock 示例看起来是否正确”，而是：

1. 任意受治理问题是否沿同一通用 Contract 流程执行；
2. LLM 决策与确定性安全职责是否清楚；
3. Mock 规则是否可能污染正式路径；
4. 指标、图表、总分析和 Evidence 是否由问题与真实数据驱动；
5. 多轮复用、失败、分页、超时、权限、恢复是否在全链路成立；
6. 内网能否只提供真实输入和配置，而不重写核心系统。

方法包括源码责任审查、架构 import 扫描、Pydantic/OpenAPI drift、单元/集成/Golden、真实 HTTP/API 探测、Chromium E2E、重复语义编译、正式 cutover 静态门禁和浏览器最终形态检查。

## 3. 本轮发现并修复的系统性问题

| 严重度 | 根因 | 影响 | 修复与回归 |
|---|---|---|---|
| 高 | “新分析 + 图表要求”在已有 Session 中可能被 Mock Agent A 误判为 PRESENTATION_CHANGE | 复用旧数据、零查询，回答了错误问题 | 新增数据签名守卫；指标/维度/grain/time/filter 任一变化强制 requery；混合问题回归 |
| 高 | 复用上下文只保存字段并用集合签名，未保存逐任务结构和统计方法 | “分别按 A/B”可能与“A×B 联合分析”等价，方法变化也可能漏查 | ActiveAnalyticalContext 保存完整 task；按每个 task 的 metric/dimension/有序 grain/method 计算签名；Schema/前端类型重生成 |
| 高 | 复合分页 QA 只消费首页 ExecutionRecord | 后续页 shard failure/timeout 可能漏报完整 | Phase4 汇总所有页执行记录；later-page shard failure 阻断测试 |
| 高 | 配置了总轮次超时但图执行未真正受其约束 | 图可能超时后继续占锁/无法按幂等重试 | orchestrator 统一 asyncio timeout；标记 retryable TURN_TIMEOUT；重试测试 |
| 中 | 高基数图返回伪 ACCEPT_WITH_TRANSFORM，但前端没有 Top-N/Other 实现 | 图可能截断且用户误以为完整 | 完整高基数直接安全降级表格；不声称未执行的前端变换 |
| 中 | OpenAI-compatible repair 的 schema name 仅为 json_repair | A/B/C repair 可能在部分端点发生 Schema 名称碰撞/缓存混淆 | schema name 使用 operation + 输出 Contract；差异测试 |
| 中 | 审计装饰器模型标识曾误透传给统一 LLM Protocol | 正式 Adapter 调用签名不一致 | model 只进入 allowlisted 安全审计，不透传 delegate；mypy 捕获与修复 |
| 中 | mcp profile 未显式携带 semantic input dir | cutover 只看 package，源输入仍可能指向 Mock | Compose/env/cutover 增加非 Mock Semantic Input 门禁 |
| 中 | Playwright 自带 webServer 在 Windows 测试完成后可能挂住 | 自动化结果通过但进程不退出 | 改为同一 Python 进程托管静态服务并清理；npm test:e2e 可正常退出 |
| 中 | pytest 固定仓库 basetemp/cache 会在 Windows/并发运行产生锁冲突 | 大量测试在 setup 前环境失败 | 移除固定 basetemp 和 cacheprovider 依赖；正式目录全量 291 通过 |
| 中 | Agent C required task 缺失只依赖一次输出 | 总分析可能合法但不完整 | required task→claim/limitation 完整性校验 + 两次定向 repair + PARTIAL |
| 中 | 总分析曾可能截断/重复 | 关键发现不完整或重复展示 | 使用全部去重 Grounded Claim 作为总分析；补充发现只显示未纳入项 |
| 中 | 技术聚合/QA 留在主 Dashboard | 用户难读，Evidence 边界错误 | 聚合表、计算、QA 统一 Evidence；主页面过滤技术块 |
| 中 | 图表数量/指标存在固定化风险 | 普通问题看似总是同一 Dashboard | KPI 仅取本轮受治理决策；图表 0/1/N；显式 line/heatmap/table 和不同维度回归 |
| 高 | 候选图与结论分开生成后可能靠标题/关键词误配 | 图能画但结论不属于该图 | Agent C 双阶段；Preview/Claim 显式 ID；task/Dataset/measure/Evidence 五项一致性校验 |
| 中 | 同 Dataset/intent 的不同指标会被过度去重 | 合法的多指标比较丢图 | 去重键加入最终 encoding；跨指标回归 |
| 高 | Agent B 只有 resolved field ID，没有字段 description/类型/能力/兼容性/基数 | 真实模型可能规划出信息不足或超桶预算的数据集 | 新增无 physical path 的 ResolvedFieldDescriptor；Agent A 候选补齐安全语义元数据；跨层测试 |
| 高 | Mapping 需手工列索引且 QueryPlan 前无受控字段画像 | 漏月、旧 Mapping、高基数或缺失字段可能到取数后才暴露 | MCP index discovery + staging Policy + `size:0` FieldProfile + mapping hash/index 编译门禁 |
| 高 | Agent B 可只标记 task_id 或低估 buckets，却没有实际取得 task 维度/grain | 后续统计看似执行但数据不充分 | Finalizer 强制 required task 的 metric/dimension/grain 覆盖；预算内提升画像下界，超预算拒绝；日趋势/高基数回归 |
| 高 | 正式 profile 曾允许直接指向 `internal-template`，Mock 文本图表 parser 与固定规则又可能被误导入正式模块 | 内网 AI 可能带着模板口径或关键词规则上线 | 正式配置拒绝 template/mock 输入；Mock parser 独立为 `mock_chart_preferences.py`；15 项 cutover 递归扫描 Agent、Prompt、编排、Query、Analytics、Presentation |
| 高 | presentation/explanation 复用曾只改旧 Dashboard 或复制旧结论 | 换图没有重新探索，解释追问没有结合当前 Preview/FeatureSummary 重新分析 | 纯换图零查询但重跑 Agent C Pass 1 + Adapter；解释零查询但重跑 Pass 2 + Grounding；语义包或逐任务签名变化强制重查 |
| 高 | 不兼容的显式图型可能在偏好应用阶段丢掉任务 | 用户要求保留但任务被静默省略 | Candidate 保留并安全降级为业务表格；warning 进入证据/状态，不把技术失败做成主页面大模块 |
| 高 | week time grain 被编译为 day，统计方法未对所有受治理数值列统一执行默认参数和最小样本 | 趋势粒度和统计结论可能错误或不完整 | 统一 minute/hour/day/week/month/quarter/year 编译；AnalyticsPipeline 按 MethodDefinition 对所有适用列执行并产出 applicability |
| 高 | 统计 Claim 只指向普通行列，没有 method/result 身份 | 同一数据可被错误统计结果解释 | selector 支持 `statistic:<method>@<column>`；EvidenceRef 增加 method ID 和 result hash，Grounding 校验唯一适用结果 |
| 高 | AnalysisPlan、Candidate、Claim 的身份/证据约束不完整 | 重复 ID 会覆盖覆盖率，task 可引用 rejected metric，空 binding 文案可绕过 Grounding | Validator 拒绝重复 task/metric decision、未选中指标；Explorer 拒绝重复 Candidate ID；Grounder 拒绝空或重名 binding |
| 中 | `AnalysisPlan.max_queries` 未端到端约束 | Agent B 可能在合法上限外扩张查询 | Finalizer/Consolidator 按服务器预算拒绝超限，Agent A 不能扩大注入预算 |

## 4. 分层验证结果

| 层 | 已验证事实 | 结果 |
|---|---|---|
| Contract | 41 个权威 JSON Schema snapshot；57 个 OpenAPI/TS schema | PASS |
| 静态质量 | Ruff、format、mypy 132 source files | PASS |
| 后端 | 单元、集成、架构、契约、G01–G25 | 291 PASS |
| 前端 | ESLint、TypeScript、7 个 Vitest 文件/19 用例 | PASS |
| 构建 | Vite production build | PASS，有 bundle size warning |
| 浏览器 | Chromium 会话隔离/恢复/安全图表/Evidence | 1 PASS |
| Semantic | 同输入两次编译、12 文件逐 hash 一致 | PASS；sp_5f523f5d403098ae |
| Cutover | 正式模拟配置、Mock/模板/固定 task 隔离、动态目录、Compiler DSL 边界 | 15/15 PASS |
| API 实测 | 新分析、纯换图复用、实质新问题重查、多指标 | PASS |
| 安全 | raw DSL/write/prompt/owner/CSV/XSS/Evidence ACL | PASS |
| 依赖与 readiness | uv locked sync、npm ci、npm audit、Mock ready endpoint | PASS；0 vulnerabilities |

## 5. 指标与计算核查

- KPI 只来自 AnalysisPlan 中 required/recommended、已注册、已计算且质量可用的 MetricDefinition。
- message_record_count 是记录数，不在未确认时伪称业务发送量。
- failure_rate 保留公式、numerator、denominator、excluded、minimum denominator 和 quality；internal-template 默认不启用未确认率口径。
- 月/分类/总计 Reconciliation、率范围、空分母、部分结果、shard failure、高基数和 composite 完整性均有 QA。
- 前端只格式化后端结果，不计算指标或拼接新业务数。

## 6. 可视化与 Dashboard 核查

- 总分析位于最前，已出现的关键发现不重复。
- 关键 KPI 数量不固定，允许 0/1/N。
- 图表数量不固定，允许 0/1/N；每图必须回答不同问题。
- Agent C 先决定值得探索的关系，Adapter 返回最终 encoding/剖面，Agent C 再同时生成图结论；不是先画图再按文本匹配。
- 每张图展示“本图回答、从图中可看出、如何阅读、解读边界”，findings 必须 Grounding。
- 用户显式 line/heatmap/table 可识别；兼容时采用，不兼容时有解释并降级。
- 图表只消费真实 Dataset grain/columns，不把同一 category 同时作为轴和重复 series，避免重复 SMS/EMAIL。
- 高基数、部分结果、空结果和不完整 series 不伪装成完整可视化。
- SafeChart 只接受声明式白名单 option 构造，不执行 LLM raw option、HTML 或 JavaScript。
- 当前 renderer 为 ECharts；Plotly 未实现/未启用，扩展必须新增受控 Adapter，不能让 LLM 自由执行绘图库。
- 主 Dashboard 不再承载“验证明细（聚合明细与指标口径）”和整块 DataQA；这些进入 Evidence。

## 7. 叙事与结论核查

Mock 总分析较简单的根因不是 Dashboard 架构，而是 RuleBasedMockLLMClient 只产生有限的结构回归 Claim。正式 Agent C Prompt 和 Contract 已要求：

- 逐一覆盖 required task 或写 limitation；
- 直接回答问题，不输出空占位语；
- 趋势、比较、集中度、构成、异常、分组差异只在证据支持时出现；
- 所有数字和类别经过 Grounding；
- 不写无证据因果或基准；
- Claim 数量由问题决定。

内网必须用真实模型做分析质量 Shadow，不能把 Mock 规则扩写为生产业务逻辑。

## 8. 未完成的外部条件

阻塞真实上线、但不阻塞代码交付：

1. 真实 Excel/CSV、Mapping 和索引覆盖未提供；
2. 真实 LLM/MCP endpoint、Secret、证书和网络不可访问；
3. failure/status/时区/敏感等级等业务口径未签字；
4. 当前主机没有 Docker，未执行真实 image build/profile run；
5. 当前主机 Node 是 24.14.1，不是发布锁定的 22.17.0；分层前端门禁通过，CI 固定 22.17.0；
6. npm audit 已在获准联网后通过并返回 0 vulnerabilities；发布环境仍须在 Node 22 上复跑相同门禁；
7. 真实 Shadow、业务 Owner verdict、生产 Ingress/身份仍由内网完成。

这些条件的脚本、配置、停止条件和检查顺序已经完整写入 INTERNAL_AI_START_HERE.md。

## 9. 非阻塞观察

- Starlette TestClient 报一条上游 deprecation warning；不影响当前 API 行为。
- Vite 报 ECharts 相关单 chunk 约 878 kB、gzip 约 292 kB 的性能 warning；构建、E2E 和安全均通过。若后续优化，必须保持 SafeChart Contract 与行为不变。

## 10. 最终信心评级

工程与 Mock 验收：Ready to share。

真实生产上线：Share with caveats / 必须完成内网真实输入、probe、Shadow 和 Owner 签字。

不存在已知核心工程 TODO。若内网发现问题，应按对象链定位根因并补全通用回归，不能针对单一问句或单一图表打补丁。
