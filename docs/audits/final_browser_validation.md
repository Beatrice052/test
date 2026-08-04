# 最新构建真实浏览器复验

日期：2026-08-04

结论：PASS。复验使用当前工作区最新生产构建、Mock 后端和真实 Chromium 页面交互，不使用静态截图代替执行结果。

## 复验场景

1. 复合问题：`分析2026年5月至7月的消息量趋势、各渠道排名和各渠道状态构成`。
   - Agent A 拆为趋势、排名、构成 3 个 required task。
   - QueryPlan 用 1 个可支撑全部任务的受治理查询取得数据，不是一图一查。
   - Dashboard 动态生成 3 张图：line、bar、stacked_bar；没有固定生成 4 张图。
   - 总分析给出 269 条、SMS 200 条、7 月 155 条峰值等已验证结论。
   - 每张图都展示“本图回答、从图中可看出、如何阅读”和证据核查提示。
2. 证据：Evidence API 返回 7 个业务数据表、1 个指标定义和 6 个对账结果；高级层包含 1 个 QueryPlan step 和 1 个已编译 DSL。`raw_documents` 明确被移除。
3. 仅换图追问：`把上一个结果改用点图展示`。
   - `turn_kind=PRESENTATION_CHANGE`，指向原回答作为 chronological parent 和 analytical base。
   - 新旧答案的 QueryPlan hash 完全一致；流式阶段不出现 QueryPlan、DSL、Search 或 Analytics 重跑。
   - 仅对兼容的排名 Dataset 生成 dot chart，其余不兼容关系降级为数据表，不伪造点图。
4. 空会话：修复禁用 detail query 仍显示“正在恢复分析现场”的条件错误；最新构建验证 `loading-panel=0`、空画布可见、输入框可用。
5. 自动化复核：Frontend ESLint、19 个 Vitest、production build 和 Chromium Playwright G02/G15/G25 全部通过；Playwright 覆盖业务证据优先、DSL 仅在高级页签展示。

## Mock 边界

本轮本地运行使用 `RuleBasedMockLLMClient` 与 Mock OpenSearch Gateway，只用于无凭证的确定性回归。正式内网 profile 必须切换到 `openai_compatible` LLM Adapter 和 MCP Gateway，并通过 15/15 cutover gate；不得把 Mock rule 扩写成生产意图、QueryPlan、DSL 或洞察逻辑。
