# 内网轻量接入与 Phase 8 Shadow 手册

内网 AI 在执行本文前必须先完整阅读 [INTERNAL_AI_START_HERE.md](INTERNAL_AI_START_HERE.md)、[受控多 Agent 架构](multi_agent_orchestration.md)、仓库根目录 `AGENTS.md` 和 [需求追踪矩阵](../requirements_traceability.md)。本文是操作步骤摘要，完整责任边界和故障处理以前述文档为准。

## 0. 允许边界

内网只提供真实 Excel、真实 Mapping、MCP/LLM 配置与 Secret、failure/status 业务确认、真实数据 Shadow。原则上只改：

```text
config/internal*.yaml
semantic-input/internal/**
.env（不提交）
adapter-specific config
evals/golden/internal/**
docs/gates/internal-*.md
```

若需要修改 `contracts/`、`orchestration/`、`query/`、`analytics/`、`presentation/`、Session/Evidence/权限代码，停止接入并反馈外网框架缺陷。

## 1. 离线验包

```powershell
./scripts/verify-package.ps1
```

必须通过 lockfile 安装、Mock Semantic compile、当前分支 275 个 backend tests、G01–G25、frontend type/lint/19 unit/build、Playwright G02/G15/G25、Mock readiness。失败即外网交付问题，不进入真实接入。

## 2. Adapter 探测

1. 用 `config/internal.example.yaml` 创建无凭证的 internal config；
2. Secret/环境变量注入 endpoint/key/auth/cert；
3. 以 `config/real-llm.env.example` 配置正式 profile；
4. `./scripts/check-real-llm-cutover.ps1`，必须证明没有 Mock/规则污染；
5. `./scripts/probe-mcp.ps1 -Config ...`；
6. `./scripts/probe-llm.ps1`。

MCP probe 只探测 Tool/schema/health，不执行业务 DSL。LLM probe 不发送业务数据。

真实 LLM 的四个主 operation（Agent C 含两个固定 Pass）、A/B/C 各自 repair schema、严禁迁移的 Mock 函数、日志字段、12 项切换门禁、Shadow 断言和失败回滚详见 [真实 LLM 切换手册](real_llm_cutover_runbook.md) 与 [双阶段可视化架构](visualization_agent_architecture.md)。正式 LLM 失败不得静默回退到 `rule_based`。

## 3. Mapping 与 Semantic

用已审核 Dataset pattern 执行 `snapshot-mapping`，由 Adapter 调 ListIndex 固化 exact indices 并获取 Mapping；使用 `prepare-internal-input` 组装 Excel description 和 Registry；先 `compile-internal-semantic` 到 staging，让敏感性和 Policy 生效；再执行 `snapshot-field-profile`，只对 model-visible/aggregatable 字段做 `size:0` 聚合画像；最后带 Profile 重编译正式候选。人工审核 Import Report、profile/mapping hash、阻塞冲突、time/channel/status、text/keyword、nested、Mapping-only 和 sanitizer events。

## 4. 业务语义确认

最少确认：一条文档含义、“消息记录数/发送量”称谓、主时间字段、Channel、status 全量分组、failure numerator/denominator、Pending/Unknown/Null、minimum denominator、敏感/禁止明细。未确认项保留 Caveat 或禁用 Metric，不由 AI 补齐。

## 5. 真实只读 Smoke

执行 `smoke-mcp`。只在 Health/list/mapping 通过后依次运行 narrow count、channel、channel×status、multi-month；检查 timeout、Shard、bucket、timezone 和 total。禁止一开始运行复杂 Dashboard。

## 6. Shadow 双跑

对每个真实 Golden 导出 AnalysisPlan、QueryPlan、Compiled DSL、Normalized Dataset、Metric result、Dashboard/Evidence 和可选 old result。使用 `build-shadow-report` 生成 hash 审计记录；比例指标加 `--require-ratio-evidence`。差异只能归入基线的七种 classification，业务 Owner 给出 PASS/FAIL/NEEDS_REVIEW。

## 7. 上线判定

完成 `docs/internal_checklist.md`；保存 `docs/gates/internal-shadow-gate.md`。真实 Shadow 未通过前保留旧系统入口，不做 Big Bang 切换。

## 8. 流式进度与代理

前端已使用 `/api/v1/chat/stream` 展示真实节点阶段，并在最终答案出现后自动收起。内网只需让 Ingress/API Gateway 对 `text/event-stream` 关闭 buffering/cache/压缩聚合，把 read timeout 设置为大于 turn timeout，并验证断连可向上游传播。详见 [流式分析进度设计](streaming_progress_design.md)。
