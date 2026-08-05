# 内网输入清单

## REQUIRED（上线前必须）

| 输入 | 最低内容 | Owner/验收 |
|---|---|---|
| Index family 与月份覆盖 | pattern、实际 exact indices、首末月份、timezone、滚动/归档规则 | OpenSearch Owner |
| Mapping snapshot | 每月真实 Mapping、类型、keyword/date/numeric 可聚合路径、mapping hash | 数据平台 |
| 字段目录 | Excel/CSV description、alias、business domain、maturity、owner、semantic type 线索 | 数据/业务 Owner |
| Policy | allowed dataset/index、blocked/sensitive/detail-allowed field、tenant/role 规则、脱敏要求 | 安全 Owner |
| MetricDefinition | ID/version/level、业务定义、Formula AST、分子分母、ValueDictionary、源字段、unit/precision、null/pending/unknown、minimum denominator、timezone、Owner | 指标 Owner |
| MeasureDefinition | source semantic field、允许/default aggregation、参数、unit、population/source grain、additive semantics、approximate | 数据 Owner |
| ValueDictionary | 原始值→受治理组、null group、版本、source field | 业务 Owner |
| EntityDefinition | identifier/label field、resolution 模式、允许的 dictionary 或 approved lookup Adapter | 业务/安全 Owner |
| MCP | approved transport、endpoint/command、只读 tool bindings、TLS、timeout/page/response limits | 平台 Owner |
| LLM | approved base URL、model/deployment、API key secret、strict JSON Schema 支持、timeout | AI 平台 Owner |
| Identity | trusted header 来源、subject/roles/tenant、反向代理清洗与注入规则 | IAM/安全 |
| 真实 Golden | 问题、scope、预期计划、实际数字、可接受图表/限制、Owner verdict | 业务验收人 |

## OPTIONAL（提高质量，不阻止首轮 Shadow）

- Policy-safe field profile：document/non-null/missing/cardinality、少量允许样例值、profile time/hash。
- Recipe：只提供候选任务/方法/可视化意图，不自动展开固定流程。
- 自定义 MethodDefinition 默认参数与适用性说明；执行仍须映射到已有受治理 Host 方法。
- Entity label/alias dictionary、业务术语词典、历史查询同义表达。
- 旧系统输出，用于 Shadow 差异分类；不能作为新系统真值的唯一来源。

## LATER（可在首轮 UAT 后版本化）

- 新的受治理统计方法或新 renderer；必须同时补 Contract、Host 实现、安全验证、Evidence 和测试。
- 经过 Policy 审批的明细查询能力；默认主路径仍为 `size:0` 聚合，不能借 Evidence 开放无限 `_source`。
- 大规模 artifact 外部对象存储 Adapter；必须保持 owner lookup、hash、生命周期和审计接口不变。

## 不得提交仓库

真实凭证、`.env`、私有证书、真实原始数据、未脱敏 Mapping/Profile/Excel、生产 artifact、Shadow 导出及用户身份信息。真实输入应放在内网受控工作区，并由发布系统生成/注入 compiled package 与 Secret。
