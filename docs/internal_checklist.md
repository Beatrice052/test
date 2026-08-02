# 内网上线前 Checklist

## Semantic

- [ ] 已完整阅读 `AGENTS.md` 与 `docs/integration/INTERNAL_AI_START_HERE.md`
- [ ] 正式 `CHATBI_SEMANTIC_INPUT_DIR` 与 Package 均指向已审核非 Mock 目录
- [ ] 同一真实输入重复编译的 package_version、文件清单与逐文件 hash 一致
- [ ] description 表已成功导入
- [ ] 目标月与相邻月 Mapping Snapshot 已保存并有 hash
- [ ] Import Report 无阻塞冲突
- [ ] 时间字段与 `Asia/Hong_Kong` 已确认
- [ ] Channel/Status/Message ID 粒度已确认或有明确 Caveat
- [ ] Value Dictionary 已审核
- [ ] 敏感字段已分类

## Metric

- [ ] 文档记录业务名称已确认
- [ ] failure_rate.v1 分子/分母已确认
- [ ] Pending/Unknown/Null 已确认
- [ ] minimum denominator 已确认
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
- [ ] `check-real-llm-cutover` 12/12 PASS
- [ ] `probe-llm` strict JSON Schema 探测 PASS
- [ ] Agent A/B/C 三个 operation 均有真实端点审计记录
- [ ] AnalysisPlanDraft、QueryPlanDraft、InsightDashboardDraft 三类 repair schema name 可区分
- [ ] 正式 Agent/编排未 import 或复制 `rule_based`/fixture/recorded 逻辑
- [ ] 真实 LLM 失败不会静默回退到 Mock
- [ ] Agent B 只输出 QueryPlan；最终 DSL 仍由确定性 Compiler 生成
- [ ] 真实多轮、非固定维度和 0/1/多图 Shadow 已通过
- [ ] required task 均有 Grounded Claim 或明确 limitation
- [ ] 数据签名变化必定 requery，纯展示/解释才允许零查询复用

## Result / Presentation

- [ ] month×channel 不丢维度
- [ ] Dataset 与旧/权威结果对账
- [ ] Claim Grounding 100%
- [ ] 图表不重复、不误导
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
