# 运维、故障排查与回滚

## Readiness 与观测

`/api/v1/health/ready` 必须确认数据库、checkpoint、artifact 目录、semantic package 和当前 profile 的 LLM/Gateway 可用。日志使用 correlation/session/turn/query/artifact ID 与 error code，禁止完整 raw response、Secret、Authorization、prompt 或敏感字段值。建议监控：turn latency、LLM repair/timeout、MCP retry/timeout/shard failure、query/page/bucket/bytes、QA status、grounding reject、artifact write/read/hash mismatch、HTTP 4xx/5xx。

## 常见故障

| 现象 | 首查 | 允许处理 | 禁止处理 |
|---|---|---|---|
| LLM schema/repair 失败 | operation、model strict schema、timeout、cutover report | 修 Adapter/Prompt/模型部署并 Shadow | 自由文本解析或切 RuleBased |
| Agent 选错字段/任务 | retrieval candidates、description/capability、A 输出 | 修 semantic description/Prompt 并回归 | 在编排加关键词 if |
| Query 被 Finalizer 拒绝 | required task、grain、cardinality/bucket budget | 修 B Prompt/profile/配置或澄清 | 让 LLM 写 DSL |
| Mapping incompatibility | exact monthly mapping/hash | 修 Mapping/index family 或重编 package | 静默忽略月份 |
| MCP timeout/page limit | endpoint、tool binding、page/bytes limits、shard | 有界重试、缩小合法 scope、扩容评审 | 标记 incomplete 为 complete |
| Metric 对不上 | source table、dictionary/version、Formula AST、timezone | Owner 确认新版本并全链重算 | 前端补公式或口头修数 |
| Artifact 409 | Answer reference、文件、size、SHA-256、目录权限 | 从同一 query 重跑生成新 Answer | 跳过 hash 校验 |
| Evidence 无 Claim Trace | Grounding failures、table/value path、used definitions | 修 C2 结构化引用或 Host mapping | 引用 LLM free-text 数字 |
| 无图或降级表 | C1 candidate、feasibility、Dataset shape/completeness | 修数据/Prompt/definition；诚实 limitation | Host 固定补四图 |

## Database 与 artifact

本升级没有新增数据库表：Evidence metadata 随不可变 AnswerSnapshot 持久化，大 JSON 写入 artifact 目录。部署前仍须备份 SQLite/Postgres 和 artifact 目录并验证可恢复性。Answer 与 artifact 必须同一保留策略；清理孤儿 artifact 应由经过审计的离线作业按 Answer 引用扫描，不能按用户输入路径删除。

## 回滚

1. 停止新流量并记录当前 commit、semantic package version、数据库和 artifact checkpoint。
2. 将应用镜像/代码回滚到最近已批准 commit；将 `CHATBI_SEMANTIC_PACKAGE_DIR` 指回对应已批准 package。
3. 不回写或删除已生成 AnswerSnapshot/Artifact；旧应用若不理解 Evidence v2，应只读保留，必要时暂时关闭新 Evidence 下载入口。
4. 若只回滚 semantic package，确认 active session 的 package/task signature 变化会强制 requery，不能复用旧 Dataset 产生新口径答案。
5. 运行 readiness、Mock/full gate、LLM/MCP probe、只读 smoke 和至少一例真实 Golden。
6. 由业务/数据/安全 Owner 决定恢复流量；记录根因、受影响 answer IDs 和重新分析计划。

安全事件（Secret 泄漏、越权 artifact、write tool 绑定）应立即停止服务、轮换 Secret、保存审计证据，并由安全流程处置；不要仅靠应用重试。
