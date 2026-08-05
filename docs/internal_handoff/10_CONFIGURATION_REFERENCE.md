# 配置与环境变量参考

以根目录 `.env.example` 为唯一变量名基线。真实值由 Secret/配置平台注入。

## 应用与存储

| 变量 | 作用 |
|---|---|
| `APP_ENV` | `local`、`mcp`、`production`；正式值触发 Mock 隔离校验 |
| `APP_HOST` / `APP_PORT` / `APP_LOG_LEVEL` | HTTP 监听与日志级别 |
| `APP_DATABASE_URL` | Session/Turn/Answer/idempotency 数据库 |
| `APP_CHECKPOINT_PATH` | LangGraph checkpoint |
| `APP_ARTIFACT_DIR` | Dataset/Evidence artifact 根目录，必须可写、备份并受 ACL 保护 |

## Semantic 与身份

| 变量 | 作用 |
|---|---|
| `CHATBI_SEMANTIC_PACKAGE_DIR` | 已审核 compiled package；正式路径不能含 mock/template |
| `CHATBI_SEMANTIC_INPUT_DIR` | admin compile 使用的已审核 input；正式路径不能含 mock/template |
| `CHATBI_DEFAULT_TIMEZONE` / `CHATBI_DEFAULT_LOCALE` | 默认业务时区/locale；Metric 可声明自己的 time semantics |
| `CHATBI_IDENTITY_MODE` | 本地 `mock` 或正式 `trusted_headers` |
| `CHATBI_DEBUG_API_ENABLED` | 默认 false；仅 developer 且经审批临时开启 |

## LLM

`CHATBI_LLM_MODE`、`CHATBI_LLM_BASE_URL`、`CHATBI_LLM_API_KEY`、`CHATBI_LLM_MODEL`、`CHATBI_LLM_TIMEOUT_SECONDS`。`fixture/rule_based/recorded` 只能用于非正式环境；正式必须 `openai_compatible` 或同 Protocol 的批准 Adapter。

## Gateway/MCP

`CHATBI_GATEWAY_MODE=mcp`、`CHATBI_GATEWAY_CONFIG_PATH`、`OPENSEARCH_MCP_TRANSPORT`、`OPENSEARCH_MCP_ENDPOINT` 或 `OPENSEARCH_MCP_COMMAND/ARGS_JSON`、`OPENSEARCH_MCP_CALL_TIMEOUT_SECONDS`。旧的 `OPENSEARCH_URL/USERNAME/PASSWORD/SSL_VERIFY` 只供受控部署/兼容配置，不授权应用绕过 MCP direct 访问。

## 预算与限制

| 变量 | 默认 | 说明 |
|---|---:|---|
| `CHATBI_MAX_QUERIES_PER_TURN` | 3 | Agent B/finalizer query 数预算 |
| `CHATBI_MAX_TOTAL_BUCKETS` | 5000 | 计划 bucket 上限 |
| `CHATBI_MAX_COMPOSITE_PAGES` | 20 | composite 最大页数 |
| `CHATBI_MAX_RAW_RESPONSE_BYTES` | 10000000 | 单轮 raw/ Evidence JSON 最大 bytes；超限阻断，不截断伪装完整 |
| `CHATBI_MAX_DETAIL_HITS` | 100 | 未来/受控明细上限；默认聚合路径不读 `_source` |
| `CHATBI_TURN_TIMEOUT_SECONDS` | 90 | 整轮执行上限 |

变更预算必须附容量、完整性和安全评审；不能为了让样例通过而无限提高。配置完成后必须运行 cutover、readiness、LLM/MCP probe、只读 smoke 与真实 Golden。
