# 前端手工验收清单

> 外网 Mock 验收用于证明产品链路。内网 Connected 验收还必须结合
> `docs/INTRANET_EXECUTION_CHECKLIST.md`，不能只看页面是否显示结果。

## 准备

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000`，使用常见桌面视口（例如 1440×900）。

## 页面与依赖

- [ ] 顶部清楚显示 MOCK DATA；
- [ ] 显示 Mock OpenSearch、三个可用月度 Index、默认时间、时区和模型版本；
- [ ] Network 中没有 CDN 请求；
- [ ] `echarts.min.js` 从 `/static/vendor/` 加载；
- [ ] 控制台无 error；
- [ ] 页面没有水平滚动。

## 聊天

- [ ] 五个示例问题可点击填入；
- [ ] Enter 发送，Shift+Enter 换行；
- [ ] 请求时出现 loading；
- [ ] 请求时 input、send、clear、example 均禁用，不能重复提交；
- [ ] 用户问题和回答按时间顺序显示；
- [ ] 同一浏览器标签刷新后会话内容由 `sessionStorage` 恢复；
- [ ] 清空会话会清除 UI、创建新 session，并能继续提问。

## 组件

- [ ] count 只显示总结和 KPI；
- [ ] Failure Rate by Channel 显示 5 个 KPI、表格和柱状图；
- [ ] 每日趋势显示折线图和表格；
- [ ] 空结果显示“当前条件下没有数据”，Failure Rate 为 `—`，没有图表；
- [ ] 指标版本显示 `failure_rate.v1 / POC_DEFINED`；
- [ ] Evidence 默认折叠，可展开查看计划、Tool、DSL、结果摘要和 QA；
- [ ] 前端没有重新计算 KPI/表格/图表数值。

## 多轮与安全

- [ ] “看看最近的失败情况。”会提问 Channel/Route/日期趋势；
- [ ] 下一轮“按Channel。”继续原请求；
- [ ] “按状态分析记录分布”会澄清 `status` 与 `statusCode`；
- [ ] 请求消息正文时显示 Policy 阻断；
- [ ] 阻断响应无 Evidence、无敏感物理字段名或原始值；
- [ ] 请求 2026-09 时显示 Mock 数据范围不足；
- [ ] 请求中国移动失败率时返回 not answerable，不套用通用 failure rate。

## API 故障

- [ ] 后端不可用时页面显示可理解错误；
- [ ] QA timeout/shard/truncation 时不显示业务 KPI、表格或图表；
- [ ] 非 JSON/校验错误不会执行查询。

## 内网 Connected 追加验收

- [ ] 页面显示 `Connected OpenSearch MCP` 和真实 semantic model version；
- [ ] health 不显示 endpoint、token、证书或 provider 原始信息；
- [ ] `structured_llm` 模式断开模型后 fail closed，不返回 Mock 结果；
- [ ] `mcp` 模式断开 Gateway 后 fail closed，不读取 JSONL Mock；
- [ ] blocked/review 字段名称和别名在 Prompt/DSL/结果/Evidence 扫描为零；
- [ ] 单月与跨月问题实际命中正确的月份集合；
- [ ] timeout、partial shard、msearch item error 不显示不完整 KPI；
- [ ] Failure Rate 与批准报表对账；
- [ ] 管理语义报告接口受内网认证保护；
- [ ] Session、日志和 Evidence 符合角色隔离和留存要求。
