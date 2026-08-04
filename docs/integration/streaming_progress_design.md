# ChatBI 流式分析进度设计

## 用户体验

用户发送问题后，前端通过 `POST /api/v1/chat/stream` 建立 SSE 流。进度卡按实际工作展示：

```text
请求/安全边界
  → Agent A 意图与 AnalysisPlan
  → Agent B 逻辑 QueryPlan
  → 确定性 DSL 编译与校验
  → OpenSearch 只读检索
  → Analytics / Metric / Statistics / Data QA
  → Agent C 可视化探索 → 受控 Adapter Preview → Agent C 洞察与图结论绑定
  → Grounding / Evidence / 最终答案
```

每条事件都有 `sequence`、`stage`、`status`、`title`、`detail`、`safe_summary` 和时间。事件来自 LangGraph `stream_mode=updates` 的实际节点完成通知，不使用前端定时器伪造。

阶段内可显示已经确认的结构化结果，例如：

- “识别到用户需要：……”；
- turn relation、task 数、受治理 metric/dimension ID；
- QueryPlan step 数和 grain；
- 已编译查询数；
- 执行记录数、FeatureSummary 数、QA route；
- Dashboard block 数。

不得显示：模型私有推理、system prompt、原始模型正文、API Key、Authorization header、完整 Semantic 候选、原始 DSL 或未经 Grounding 的洞察。

## 最终结果出现时

进度组件只在 mutation 为 pending 时存在。SSE 收到 `result` 后，前端刷新 Session 的不可变 `AnswerSnapshot`；答案加载完成，进度组件自动卸载。因此用户等待时能看到实际进度，最终页面不会永久堆叠中间过程。

如果用户取消，浏览器 AbortController 关闭连接，服务端取消仍在运行的任务并释放 Session lock。如果流程失败，流返回安全的 `error` envelope，不把服务端 exception、prompt 或数据正文返回浏览器。

原 `POST /api/v1/chat` 保留，供不支持 SSE 的客户端兼容；两条入口调用同一个 Orchestrator，最终 `ChatApiResponse` 和不可变 Answer 没有两套业务逻辑。

## SSE 事件示例

```text
event: progress
data: {"event":"progress","progress":{"sequence":1,"stage":"request",...}}

event: progress
data: {"event":"progress","progress":{"sequence":9,"stage":"search",...}}

event: result
data: {"event":"result","result":{"status":"COMPLETED",...}}
```

服务端响应头包含：

```text
Content-Type: text/event-stream
Cache-Control: no-cache, no-transform
X-Accel-Buffering: no
```

空闲 15 秒会发送 SSE comment heartbeat，避免中间网络设备误判连接空闲。

## 反向代理/Ingress

项目 `frontend/nginx.conf` 已关闭 `/api/` 的 buffering/cache，并把 read timeout 提高到 600 秒。内网额外的 Nginx/Ingress/API Gateway 也必须等效配置：

```nginx
proxy_http_version 1.1;
proxy_buffering off;
proxy_cache off;
proxy_read_timeout 600s;
add_header X-Accel-Buffering no;
```

若代理启用了响应压缩或聚合缓冲，要为 `text/event-stream` 关闭，否则服务端虽然逐条发送，用户仍会一次性收到全部内容。代理超时必须大于 `CHATBI_TURN_TIMEOUT_SECONDS`，并允许客户端断连向上游传播。

## 内网验证清单

- 浏览器 Network 中 `/chat/stream` 为 pending，事件逐步到达而不是最后一次性到达；
- Agent A/B/C 的阶段与服务端实际 operation 一致；
- 展示复用场景明确显示“不重新检索 OpenSearch”；
- Clarification/Forbidden/QA failed/Gateway failed 都能结束流；
- 取消请求会停止后台 turn 并释放 lock；
- 最终 Answer 出现后进度区消失；
- progress payload 不含 `query_dsl/system_prompt/chain_of_thought/api_key`；
- 60–180 秒长查询不被代理提前关闭；
- 多用户并发事件不串流、不跨 subject。
