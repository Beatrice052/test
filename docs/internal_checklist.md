# 内网上线前 Checklist

## Semantic

- [ ] 已完整阅读 `AGENTS.md`、`docs/integration/INTERNAL_AI_START_HERE.md` 与 `docs/integration/decision_authority_matrix.md`
- [ ] 正式 `CHATBI_SEMANTIC_INPUT_DIR` 与 Package 均指向已审核非 Mock 目录
- [ ] 正式 Semantic Input/Package 路径不含 `internal-template`；模板 Recipe 已按真实业务删除或审核
- [ ] 同一真实输入重复编译的 package_version、文件清单与逐文件 hash 一致
- [ ] description 表已成功导入
- [ ] 目标月与相邻月 Mapping Snapshot 已保存并有 hash
- [ ] Import Report 无阻塞冲突
- [ ] 时间字段与 `Asia/Hong_Kong` 已确认
- [ ] 实际分类、状态、主键/记录 ID 与时间粒度已确认或有明确 Caveat；不得照抄 Mock 字段名
- [ ] Value Dictionary 已审核
- [ ] 敏感字段已分类

## Metric

- [ ] 文档记录业务名称已确认
- [ ] 每个认证率指标的分子/分母、排除项和版本已确认
- [ ] 每个 Value Dictionary 的未知/空值/待处理语义已确认
- [ ] 各率指标 minimum denominator 已确认
- [ ] Metric Owner/版本/生效日期已记录
- [ ] 真实数据 numerator/denominator/excluded 对账通过
- [ ] 未认证指标未显示为正式 KPI

## Query / MCP

- [ ] 只读账号或只读 IAM/mTLS 策略
- [ ] exact index allowlist
- [ ] MCP required binding 全部 found
- [ ] Generic API/PPL/Memory/写 Tool 未绑定
- [ ] scripts 禁止
- [ ] Bucket/timeout/detail/response limit
- [ ] Terms 截断可检测
- [ ] Composite 分页通过
- [ ] 后续 Composite 页 shard failure/timeout 会进入 QA 并阻断完整答案
- [ ] 月份/时区 Golden 通过
- [ ] 固定只读 smoke 全部 PASS 且无 failed shard/timeout

## Real LLM

- [ ] `APP_ENV=mcp` 且 readiness 显示 `openai_compatible · mcp`
- [ ] `check-real-llm-cutover` 15/15 PASS
- [ ] `probe-llm` strict JSON Schema 探测 PASS
- [ ] Agent A、Agent B、Agent C 两个 Pass 的四个主 operation 均有真实端点审计记录
- [ ] AnalysisPlanDraft、QueryPlanDraft、InsightDashboardDraft 三类 repair schema name 可区分
- [ ] 正式 Agent/Prompt/编排/Query/Analytics/Presentation 未 import 或复制 `rule_based`/fixture/recorded 逻辑
- [ ] 正式路径未导入 `mock_chart_preferences`，也不存在固定趋势/排名/构成 task bundle
- [ ] Agent A 与 Plan Validator 的 visualization catalog 来自当前 Semantic Package，而非 Python 固定问题映射
- [ ] 真实 LLM 失败不会静默回退到 Mock
- [ ] Agent B 只输出 QueryPlan；最终 DSL 仍由确定性 Compiler 生成
- [ ] 通过 `ListIndexTool` 固化 exact index list，Mapping Snapshot 与目标月份一致
- [ ] staging 编译先应用 Excel description、敏感等级与 Policy；FieldProfile 只覆盖 model-visible/aggregatable 字段
- [ ] FieldProfile 查询固定 `size:0`，不含 `_source`/raw documents；dataset/index/mapping hash 校验通过
- [ ] Agent A 候选和 Agent B `ResolvedFieldDescriptor` 均包含真实 description、能力、兼容性和 cardinality 摘要，且不含 physical path
- [ ] Agent B 的 QueryPlan 对每个 required task 取得最小充分粒度；高基数和跨月不兼容走预算/路由失败路径
- [ ] 真实多轮、非固定维度和 1/多图 Shadow 已通过；空/QA 阻断场景只显示真实不可用状态
- [ ] AnalysisPlan 的 task/metric decision ID 唯一，task 没有引用 rejected/未选中指标
- [ ] required task 均有 Grounded Claim 或明确 limitation
- [ ] `post_query_visual_exploration` 只输出 Contract 化的 AnalyticsToolRequest/Candidate，`post_query_insight_dashboard` 只使用返回的统计结果和验证 Preview
- [ ] Candidate ID 唯一；每条 Claim 至少有一个且名称唯一的 binding
- [ ] 每张图与 Claim 的 task、Dataset、measure、EvidenceRef 完全一致
- [ ] 统计 Claim 的 EvidenceRef 可定位 method ID、source column 与 statistical result hash
- [ ] scope 或任一 task 的 metric/dimension/grain/statistical method 变化必定 requery
- [ ] 纯换图零查询但重跑 Agent C Pass 1；解释追问零查询但重跑 Pass 2

## Result / Presentation

- [ ] 每个实际多维/联合粒度结果都不丢维度；不得把 Month×Channel 等示例写成固定形态
- [ ] Dataset 与旧/权威结果对账
- [ ] Claim Grounding 100%
- [ ] 图表不重复、不误导
- [ ] 非空且 QA 可用的 ChatBI 结果具有 Agent C 选择的 1/N 图；没有固定四图、固定二维形态或固定业务字段，也没有程序自选 fallback 图
- [ ] 每张图均有业务目的、Grounded findings 和必要 caveat；UI 没有机械“本图回答/如何阅读/证据提示”模板
- [ ] C1 的统计请求只使用实际 Dataset numeric metric/measure、注册 MethodDefinition 和允许参数；APPLICABLE/NOT_APPLICABLE 均可在 Evidence 核查
- [ ] C2 在统计结果和 Preview 返回后生成 overall_claim_ids、kpi_selections 和图表解释；KPI 不从 Agent A 的 metric 列表默认回填
- [ ] 已将旧项目 Owner 确认的 L1/L2 指标迁入 internal metric_registry，并完成重算/Owner verdict
- [ ] Evidence 可核查
- [ ] Business Evidence 无 DSL；Advanced Evidence 有角色
- [ ] Debug 默认关闭
- [ ] 历史 Session 可恢复

## Security / Operations

- [ ] Prompt Injection 与 terminology/description injection Golden 通过
- [ ] 跨用户 Session/Dataset/Evidence 隔离
- [ ] 敏感明细脱敏
- [ ] raw DSL 与写操作被拒绝
- [ ] Secret 不在 repo、日志、Evidence 或报告
- [ ] 身份头只由可信反向代理注入
- [ ] SSE 代理 buffering/cache 已关闭，read timeout 大于 turn timeout
- [ ] 流式 progress 不含 prompt、私有推理、原始 DSL、Key 或业务原文
- [ ] 最终 Answer 出现后中间进度自动收起
- [ ] 总轮次超时产生 retryable `TURN_TIMEOUT`，锁与执行均释放
- [ ] Backup/restore、日志保留和应急回退已演练
- [ ] Shadow 报告完成业务 Owner 签字
