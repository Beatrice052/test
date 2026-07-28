# 内网精简执行清单

## 使用规则

- I0 已完成；POC 后续只执行 I1、I2、I3；
- 一次只完成一个阶段；
- 每阶段开始记录 branch、commit、配置和测试基线；
- 每阶段结束先测试、再汇报、再等待确认；
- 真实数据、秘密、内网 URL 和生产 hits 不得进入 Git；
- Production 是可选阶段，不阻塞 POC。

## I1：真实语义模型

- [ ] 真实 Catalog 作为语义主资料并记录 version/hash
- [ ] CSV schema、duplicate、access/sensitivity 校验
- [ ] `candidate_role` 全路径隔离
- [ ] MCP `list_indices/get_mapping` 自动取得相关月份 Mapping
- [ ] 字段存在性、物理类型、keyword/date/object/nested 和聚合能力校验
- [ ] 多月 Mapping drift 报告
- [ ] Catalog-only 不可查询
- [ ] Mapping-only/缺少 access 默认 review_required
- [ ] 类型冲突和不兼容 drift fail closed
- [ ] 确认真实时间字段
- [ ] `failure_rate.v1` 绑定 `status`，不绑定 `statusCode`
- [ ] CompiledSemanticModel、Import Report、version/hash
- [ ] semantic compilation 共享和版本 mismatch 测试
- [ ] `production_policy_rbac_status=pending`
- [ ] 完整质量命令通过

Gate：真实 Catalog 可编译，Mapping 物理能力经过校验，无未解释 fatal conflict。
生产 Policy/RBAC 不属于本阶段 Gate。

## I2：真实 LLM + OpenSearch MCP 端到端接入

- [ ] 研读获批内网 LLM 项目并实现 `StructuredLLMTransport`
- [ ] structured output、timeout、retry、refusal 和日志脱敏
- [ ] Prompt 只包含 allowed 字段
- [ ] blocked/review/candidate_role Prompt 扫描为零
- [ ] 实现 `AllowedMCPToolClient` 五项窄能力
- [ ] 无 PPL、Generic API 或任意 path
- [ ] count/search/msearch 响应和错误归一化
- [ ] timeout、partial shard、msearch item error fail closed
- [ ] 真实 LLM/Gateway/semantic compilation 显式注入
- [ ] 真实模式无 Mock fallback
- [ ] 单月、分组、趋势、Top N、跨月、澄清、空结果、blocked、Evidence
- [ ] 全部场景经 `/api/chat`
- [ ] `production_policy_rbac_status=pending`
- [ ] 完整质量命令通过

Gate：真实 LLM 和 MCP 已通过同一 `/api/chat` 主链路，错误不会产生不完整业务结论。

## I3：指标对账和 POC 最终验收

- [ ] record_count.v1 对账
- [ ] failure_rate.v1 总体、每日、Channel、Route 对账
- [ ] 单月和跨月边界
- [ ] null/unknown/retry/duplicate/零分母/舍入
- [ ] 差异根因明确，不静默修改 v1
- [ ] carrier/statusCode 资料齐全则新增独立指标；缺失不阻塞通用 POC
- [ ] Golden 全部经 `/api/chat`
- [ ] KPI/table/chart/clarification/no-data/blocked/Evidence
- [ ] LLM/MCP timeout 和 partial error
- [ ] Mock/Connected 状态明确
- [ ] 前端手工验收
- [ ] 未完成生产化事项明确
- [ ] 完整质量命令通过

Gate：通用 ChatBI POC 有完整对账、E2E、故障和前端验收证据。

## 可选 Production：生产化加固

只有项目负责人明确授权才执行：

- [ ] 生产 Policy/RBAC
- [ ] 身份认证和管理接口保护
- [ ] secret/TLS/证书
- [ ] 持久化、隔离的 Session
- [ ] 日志、Prompt、Evidence、审计和留存
- [ ] 限流、并发、SLO 和性能压测
- [ ] 全面故障演练
- [ ] 部署和回滚
- [ ] 生产业务/安全/平台验收

Gate：全部有证据后才能声明 production-ready。

## 每阶段报告

报告至少包含：

```text
阶段和日期
branch/commit/config version
使用的真实来源
创建或修改文件
实现能力
执行测试和完整结果
安全/数据处理
未完成或阻塞
回滚点
下一步建议
```

## 完整质量命令

```powershell
python -m pytest -q
python -m ruff check app tests
python -m ruff format --check app tests
python -m pyright app tests
node --check app/static/js/app.js
```
