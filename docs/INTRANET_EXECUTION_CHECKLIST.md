# 内网分阶段执行清单

## 使用规则

- 一次只完成一个阶段；
- 阶段开始前记录基线 commit/config/version；
- 阶段结束先测试，再按模板汇报并取得确认；
- 方框没有证据不能勾选；
- 真实数据、秘密和内网 URL 不得进入本清单或 Git。

## I0：认知与资料盘点

- [ ] 完整阅读 `INTRANET_START_HERE.md` 和文档索引中的必读文档
- [ ] 阅读主流程、契约、Compiler、LLM、Gateway、Metric、Validator 代码和测试
- [ ] 输出内网接手认知报告
- [ ] 找到批准的内网 LLM 参考项目及 owner
- [ ] 找到真实 Field Catalog 及版本/owner
- [ ] 获取真实 Index inventory 和多月 Mapping 计划
- [ ] 获取 MCP 实际 Tool schema/错误样例
- [ ] 找到报表口径和对账 owner
- [ ] 找到生产 Policy/RBAC owner
- [ ] 记录 carrier code 资料是否存在
- [ ] 列明全部缺失项和停止条件

Gate：项目负责人确认认知报告。本阶段不得接生产调用。

## I1：真实 Semantic Model

- [ ] 对真实 CSV 做只读 schema/重复/编码/敏感内容检查
- [ ] 验证 `candidate_role` 仍被彻底忽略
- [ ] 取得代表性及变更月份 Mapping
- [ ] 生成字段新增/删除/类型/子字段/date format drift 报告
- [ ] Mapping-only 和未分类字段默认 review
- [ ] 完成生产 blocked/review/allowed 审批
- [ ] 确认真实时间字段和聚合能力
- [ ] 确认 `status` 与 `statusCode/status_code` 不混用
- [ ] 编译真实模型并生成 Import Report/version/hash
- [ ] LLM/Resolver/Validator 共用同一模型
- [ ] 单元、安全和跨月 drift 测试通过

Gate：无未解释 fatal conflict；allowed 字段都有业务与安全依据。

## I2：真实 LLM

- [ ] 阅读批准参考项目的 client/factory/config/tests
- [ ] 记录 structured output、timeout、retry、审计、脱敏方式
- [ ] 实现 `StructuredLLMTransport`
- [ ] secret/model 配置不入仓库
- [ ] 真实模式显式依赖注入
- [ ] schema error、timeout、auth、refusal 归一化
- [ ] Prompt 只含 allowed 语义摘要
- [ ] blocked/review/`candidate_role` Prompt 扫描为零
- [ ] prompt injection 和未知字段测试通过
- [ ] `/api/chat` 澄清和 Golden 通过
- [ ] 证明 structured_llm 模式无 Mock fallback

Gate：模型只能影响 AnalysisPlan/summary，不能影响 DSL/Tool/Metric/HTML。

## I3：真实 OpenSearch MCP

- [ ] 记录五项 Tool 的实际 schema/version
- [ ] 获取成功、timeout、auth、shard、msearch item error 样例
- [ ] 实现 `AllowedMCPToolClient`
- [ ] 只有 list/mapping/count/search/msearch
- [ ] Index pattern/role/month allowlist 生效
- [ ] 请求不含 script/runtime mappings/document hits
- [ ] 响应与错误统一归一化
- [ ] partial/msearch error 不输出业务 KPI
- [ ] 日志/Evidence 无 secret/endpoint/raw error
- [ ] `/api/chat` 单月、跨月、空结果、故障测试通过
- [ ] 证明 mcp 模式无 Mock fallback

Gate：Gateway 无法绕过 Policy，业务模块无直接 MCP 调用。

## I4：指标和报表对账

- [ ] 使用批准的脱敏聚合对账集
- [ ] 总量逐日对账
- [ ] Failure Rate 总体对账
- [ ] 按 Channel 对账
- [ ] 按 Route 对账
- [ ] 跨月边界对账
- [ ] null/unknown/retry/duplicate 对账
- [ ] 零分母为 null
- [ ] 舍入为 ROUND_HALF_UP 两位
- [ ] 差异有根因、owner 和处理结论
- [ ] 真实口径不同则新增版本，不改 v1

Gate：差异在批准阈值内；版本、owner、生效范围和证据齐全。

## I5：运营商 `statusCode`

- [ ] 确认 carrier 和 code 真实字段
- [ ] 取得移动/电信/联通批准码表
- [ ] 码表包含版本、生效时间、匹配方式和 owner
- [ ] 定义空码/未知码/新码处理与告警
- [ ] 定义多回执优先级
- [ ] 新增独立 Metric ID/version
- [ ] 规则进入配置和 Metric Engine，不进入 Prompt
- [ ] 三运营商及 unknown fixture 测试
- [ ] 历史月份适用版本测试
- [ ] 与运营商报表对账

Gate：无任何由 LLM 猜测的编码；unknown 可观察且不误分成功/失败。

## I6：上线验收

- [ ] 身份认证、角色和 Index/字段权限
- [ ] secret/TLS/证书轮换
- [ ] Session 存储、TTL、隔离和清理
- [ ] API/管理接口访问控制
- [ ] 日志、trace、Evidence 保留和脱敏
- [ ] 请求/月份/桶/并发限流
- [ ] timeout、partial shard、msearch partial、LLM/MCP 不可用演练
- [ ] 常规与峰值性能测试
- [ ] Prompt/DSL/结果/Evidence blocked 扫描
- [ ] 全部 Golden 经 `/api/chat`
- [ ] 前端手工验收
- [ ] 回滚 Mock/上版配置演练
- [ ] 业务、数据、安全和平台 owner 签字/记录

Gate：只有完成本阶段才可称 production-ready。

## 每阶段报告模板

可复制到新阶段报告：

```markdown
# Phase Ix 报告

- 日期：
- 分支/commit：
- 环境：
- 使用来源及版本：

## 创建或修改文件

## 实现能力

## 安全与数据处理

## 执行测试

## 测试和对账结果

## 尚未完成/阻塞

## 回滚点

## 下一阶段计划
```

统一质量命令：

```powershell
python -m pytest -q
python -m ruff check app tests
python -m pyright app tests
node --check app/static/js/app.js
```
