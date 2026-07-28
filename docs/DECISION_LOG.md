# 决策日志与未决项

## 冻结决策

| ID | 决策 | 状态 |
|---|---|---|
| D01 | 月度 Index 为 `tbl_os_sub_message_YYYY_MM` | CONFIRMED |
| D02 | July 仅是默认时间，不是唯一数据范围 | CONFIRMED |
| D03 | 时区 `Asia/Hong_Kong` | CONFIRMED |
| D04 | 时间为 `[from,to)` | CONFIRMED |
| D05 | record count 等于 document count，不去重 | CONFIRMED |
| D06 | `failure_rate.v1` 使用 normalized `status` | CONFIRMED |
| D07 | success 为 SENT/INPROGRESS | CONFIRMED |
| D08 | failed 为 FAILED/ACKFAIL | CONFIRMED |
| D09 | null/unknown 为 Other，零分母 null | CONFIRMED |
| D10 | retry/duplicate 保留在分母 | CONFIRMED |
| D11 | `statusCode` 是运营商原始码 | CONFIRMED |
| D12 | 指标由 Metric Engine 计算，LLM 不计算 | CONFIRMED |
| D13 | Query 使用 OpenSearch DSL，不用 PPL | CONFIRMED |
| D14 | Tool 由程序在 QueryPlan 后选择 | CONFIRMED |
| D15 | Generic API 不暴露 | CONFIRMED |
| D16 | 单体 FastAPI/Jinja2/Vanilla JS/ECharts | CONFIRMED |
| D17 | `candidate_role` 全路径忽略 | CONFIRMED |
| D18 | blocked 由后端强制，不能只前端隐藏 | CONFIRMED |
| D19 | 真实模式必须显式注入 LLM/Gateway，不回退 Mock | CONFIRMED |
| D20 | 当前不用 LangGraph | CONFIRMED FOR POC |
| D21 | 真实 `field_catalog_enrich.csv` 是语义主资料 | CONFIRMED |
| D22 | Mapping 由 MCP 自动读取，只作实际物理 schema 和跨月 drift 校验 | CONFIRMED |
| D23 | 生产 Policy/RBAC 属于可选生产化工作，不阻塞 I1～I3；POC 使用 Catalog 的 access/sensitivity 和现有技术控制 | CONFIRMED FOR POC |
| D24 | `failure_rate.v1` 定义已经确认；I3 只做生产报表对账，不重新询问或定义公式 | CONFIRMED |
| D25 | I0 后的 POC 收敛为 I1 真实语义、I2 真实 LLM + MCP、I3 对账与最终验收；生产化单列可选 | CONFIRMED |

## 内网待确认

| ID | 问题 | 阻塞内容 | 需要证据 |
|---|---|---|---|
| O01 | 真实默认时间字段 | 所有查询 | Mapping + 字段 owner |
| O02 | 各月 Mapping 是否一致 | 跨月查询 | 多月 Mapping diff |
| O03 | 真实 Catalog 字段语义 | Semantic Model | 原始 CSV + owner |
| O04 | 生产 Policy/RBAC | 仅阻塞 production-ready，不阻塞 I1～I3 POC | 数据分类、角色/字段/Index 权限 |
| O05 | LLM provider/model/helper | 真实 Intent/Summary | 参考项目与平台规范 |
| O06 | MCP Tool 名称/schema | Gateway | Tool schema/样例 |
| O07 | MCP partial error 结构 | Data QA | timeout/shard/msearch 样例 |
| O08 | v1 与真实报表一致性 | 指标上线 | 对账数据 |
| O09 | carrier 字段 | 运营商指标 | Mapping/业务确认 |
| O10 | carrier code 规则 | 运营商指标 | 三运营商版本化码表 |
| O11 | Session 持久化/认证 | 共享部署 | 架构/安全要求 |
| O12 | 日志与 Evidence 留存 | 审计 | 合规策略 |
| O13 | 时间/桶/月份上限 | 性能 | 压测与 SLO |

## 决策变更规则

- CONFIRMED 变更需要记录原因、批准人、日期和影响测试；
- Metric 定义变化必须新增版本；
- Policy 变化需要安全评审；
- Mapping drift 不得通过强制 cast 静默吞掉；
- Catalog 中 `access=allowed` 只代表当前 POC 可用，不等于生产 RBAC 已批准；
- I1～I3 必须持续标记 `production_policy_rbac_status=pending`；
- 未决项在有证据前不能写成生产事实。
