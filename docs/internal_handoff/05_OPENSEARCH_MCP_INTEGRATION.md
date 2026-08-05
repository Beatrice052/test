# OpenSearch MCP 接入

## 传输与只读工具

配置入口为 `config/gateway.mcp.yaml` 和环境变量。支持 `streamable_http`、`stdio`，`sse_legacy` 仅用于被批准的旧服务。正式绑定只允许 health、list indices、get mapping、field profile/search 等受控只读能力；`GenericOpenSearchApiTool`、PPL、write/delete/update、memory 和自由 API 工具禁止绑定。

Agent 从不调用 MCP。Host Gateway 将稳定的 `MappingRequest`/`CompiledQuery` 转为已批准 tool 参数，并验证响应 schema、shard、timeout、size 和错误码。

## 配置步骤

1. 设置 `CHATBI_GATEWAY_MODE=mcp`、`CHATBI_GATEWAY_CONFIG_PATH`、transport、endpoint/command 和 call timeout。
2. 在 `config/gateway.mcp.yaml` 填写实际只读 tool 名；凭证仅使用 env/Secret reference。
3. 运行 health/probe：

```powershell
./scripts/probe-mcp.ps1 -Config ./config/gateway.mcp.yaml -Output C:\secure\reports\mcp-probe.json
```

4. 对批准的 exact indices 运行通用 smoke（1–3 个任意维度）：

```powershell
./scripts/smoke-mcp.ps1 -Config ./config/gateway.mcp.yaml -Dataset business_dataset `
  -Index @('index_2026_07') -TimeField event_time `
  -DimensionField @('region_code','product_family') `
  -From '2026-07-01T00:00:00+08:00' -To '2026-08-01T00:00:00+08:00' `
  -Timezone 'Asia/Hong_Kong' -Output C:\secure\reports\mcp-smoke.json
```

Smoke 只发 `size:0`、有 timeout、有限 terms 的 count/单维/多维/time×dimension 查询，并检查 shard、timed_out、response size 与 hash。

## 查询执行边界

- `CHATBI_MAX_QUERIES_PER_TURN`、`CHATBI_MAX_TOTAL_BUCKETS`、`CHATBI_MAX_COMPOSITE_PAGES`、`CHATBI_MAX_RAW_RESPONSE_BYTES` 和 MCP timeout 必须按容量评审。
- 低预算完整分布可用 terms；高基数 N 维使用 composite 分页。每一页都有 ExecutionRecord，失败或 page-limit 不得伪装完整。
- dependent Top-N query 只能引用前序受控 Dataset selection，不能由 LLM 猜值。
- 默认 `size:0`；明细 hits 即使 Gateway 返回也不写入 raw Evidence，未来明细能力须独立做白名单、脱敏和 size 上限。

## Raw result artifact

成功 query 的所有实际 aggregation buckets、metric values、composite page count/after keys、shard/completeness metadata 会写入 owner-mediated JSON artifact；日志只记录 ID/hash/size，不记录完整敏感响应。下载先通过 AnswerSnapshot subject ownership，再校验 artifact ID、路径、最大大小、JSON 和 SHA-256。

Readiness 必须同时检查数据库、artifact 目录、semantic package、LLM 和 Gateway。MCP 故障按错误类型有界重试；write capability、认证泄漏、mapping 变更或不一致 shard 必须阻断。
