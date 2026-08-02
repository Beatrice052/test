# MCP Adapter 接入指南

## 固定边界

真实 OpenSearch 只通过官方 Python MCP SDK transport 进入 `McpOpenSearchGateway`。LLM 不拥有 Tool，动态连接参数不来自 Agent。允许能力为 `list_indices`、`get_mapping`、`execute_search`、`health`；`GenericOpenSearchApiTool`、`PPLQueryTool`、Memory/Agentic 和写类 Tool 禁止绑定。

`local-os` 锁定 `opensearch-mcp-server-py==0.11.0`，只启用四个只读 Tool，设置 `OPENSEARCH_SETTINGS_ALLOW_WRITE=false`。生产/内网应由已批准的 MCP 服务、认证代理或受限网络提供相同 Tool schema。

## 配置

复制 `config/internal.example.yaml` 为不含凭证的 `config/internal.yaml`。只在 Secret Store、环境变量或不提交的 `.env` 中设置：

```text
OPENSEARCH_MCP_ENDPOINT
OPENSEARCH_MCP_TRANSPORT=streamable_http
```

stdio 模式可在 `gateway.mcp` 配置 `command`、`args` 和 `environment_from_env`；后者只写环境变量名，不写值。TLS verify 默认必须为 true；仅 `local-os` 无认证开发集群允许 false。

## Probe（不执行业务 DSL）

```powershell
./scripts/probe-mcp.ps1 -Config ./config/internal.yaml -Output ./reports/mcp-probe.json
```

报告包含 transport、可获取的 server name/version、detected tools、required binding found/missing、Search input schema compatibility、health、forbidden binding check，并显式记录不含 credentials。

## Mapping Snapshot

```powershell
./scripts/snapshot-mapping.ps1 `
  -Config ./config/internal.yaml `
  -Dataset sub_message `
  -Index tbl_os_sub_message_2026_07 `
  -Output ./input-real/mapping_snapshot_20260731.json
```

输出是编译器可直接读取的版本化 `MappingSnapshot`，保存 mapping hash、indices、timestamp、Tool/transport/server metadata，不保存凭证。

## 固定只读 Smoke

```powershell
./scripts/smoke-mcp.ps1 `
  -Config ./config/internal.yaml -Dataset sub_message `
  -Index tbl_os_sub_message_2026_05,tbl_os_sub_message_2026_06,tbl_os_sub_message_2026_07 `
  -TimeField event_time -ChannelField channel -StatusField status `
  -From '2026-05-01T00:00:00+08:00' -To '2026-08-01T00:00:00+08:00' `
  -Output ./reports/mcp-smoke.json
```

顺序固定为 Health → explicit index list → Mapping → narrow count → channel → channel×status → multi-month。字段和 index 参数有安全语法校验，index wildcard 被拒绝；查询固定 `size=0`、10s、`[from,to)` 和显式 timezone。报告保存 DSL、response hash、took、Shard、total、bucket count，不保存 raw 文档或凭证。
