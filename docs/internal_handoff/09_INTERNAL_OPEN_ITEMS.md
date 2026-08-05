# 仅限内网确认的事项

本文件不包含外网可实现的工程 TODO。Compiler、Agent A/B/C contracts、通用 aggregations、Analytics、Evidence、API、前端和测试框架均已实现。

| 项目 | 必须确认的结果 | Owner/签字 |
|---|---|---|
| 真实字段与 Mapping | index family、逐月 exact Mapping、field catalog、兼容性和 profile hash | OpenSearch/数据 Owner |
| 业务指标口径 | Metric version、Formula AST、分子分母、ValueDictionary、排除项、minimum denominator、timezone、unit/precision | Metric/业务 Owner |
| Policy 与权限 | tenant/subject/role、blocked/sensitive/detail/export、artifact retention、可信身份头 | 安全/IAM Owner |
| 真实 endpoint/凭证 | approved LLM model/base URL、MCP transport/tools、TLS/Secret 注入和 rotation | AI/平台 Owner |
| 真实 Golden | 代表性单轮/多轮问题、预期数字/容差、任务/图表/限制和 Evidence 对账结论 | 业务 UAT Owner |
| 上线 Owner/sign-off | Shadow/UAT report、回滚窗口、值班与故障升级联系人 | 产品/工程/安全负责人 |

在以上事项缺少时可继续使用完全合成的 Mock 开发和验证，但不得声称真实 LLM、真实 MCP、真实业务数字或生产权限已通过。
