# Phase 5 — 独立测试与最终验收

## 角色

你是独立验收工程师。不得因为 Phase 4 已完成就假设系统正确。第一轮只测试和审计，不得边测边随意修改。

---

## 阶段目标

验证：

- 后端功能没有遗漏；
- React + Vite 交互没有退化；
- HTML Demo 排版已正确迁移；
- 前后端 Contract 一致；
- Reducer/State 正确；
- 已知 Bug 未回归；
- 完整业务流程可走通；
- 项目是否适合内部 Demo 或业务 UAT。

---

## 必须先读取

```text
reports/decision-register.md
reports/phase2/03-capability-matrix.md
reports/phase2/04-bug-regression-matrix.md
reports/phase2/05-source-of-truth-map.md
reports/phase3/07-frontend-acceptance-checklist.md
recovered-main/recovery-docs/recovery-log.md
recovered-main/recovery-docs/open-risks.md
```

不得重新比较全部历史版本，除非需要验证某项来源证据。

---

## 强制限制

1. 第一轮只测试，不改代码。
2. 不得把“页面打开”当成通过。
3. 不得把“HTTP 200”当成业务通过。
4. 不得声称未执行的测试通过。
5. 不得省略失败场景。
6. 不得用 live LLM 随机结果替代确定性测试。
7. 不得忽略视觉回归和交互回归。
8. 完成后给出明确 Ready / Not Ready。

---

## Token 节省策略

1. 直接运行现有测试，不重新解释实现。
2. 失败时只定位失败链路。
3. 使用测试报告文件，不在聊天粘贴日志。
4. 只对高风险 direct mutation、API mismatch 和 workflow failure 深读源码。
5. 使用 Bug ID、Capability ID 和 Change ID 引用既有报告。

---

## 验收范围

### A. 启动与基础

- 后端启动；
- React + Vite 启动；
- 前端连接后端；
- 环境变量错误可理解；
- 无敏感信息暴露。

### B. API Contract

- Request Schema；
- Response Schema；
- Error Schema；
- 缺失字段；
- 多余字段；
- 旧接口 adapter；
- React API Client。

### C. State/Reducer

搜索所有影响以下状态的修改：

- current use case；
- form fields；
- channel；
- language；
- workflow step；
- active questions；
- highlighted fields；
- conflict；
- validation；
- Action Preview；
- InternalImpactPlan。

分类：

- reducer-driven；
- approved service transition；
- initialization-only；
- test-only；
- invalid direct mutation。

存在未解释的 invalid direct mutation，则不得 Ready。

### D. 后端功能

逐项核对 Phase 2 Capability Matrix。

### E. 前端视觉

核对：

- 9 步流程紧凑；
- 左侧模块；
- 中间表单；
- 右侧统一对话；
- Action Preview；
- Acceptance Criteria Validation 不贴边；
- 无不必要横向滚动；
- 多分辨率；
- loading/error；
- scroll；
- sticky。

### F. 前端交互

核对：

- React 组件仍负责交互；
- 表单值不丢；
- 模块切换正常；
- back navigation 正常；
- confirmation question 正常；
- 1–3 questions；
- field highlight；
- cross-module highlight；
- Action Preview；
- validation；
- workflow transition。

---

## 必跑业务剧本

### Scenario 1：全新 Use Case

验证：

- Requirement 输入；
- C 分支；
- P0；
- 依赖；
- 1–3 问题；
- 完整表单；
- 进入下一阶段。

### Scenario 2：历史 Use Case 原样复用

验证 A 分支和 ID。

### Scenario 3：修改历史 Use Case，保持原 ID

验证 B1。

### Scenario 4：修改历史 Use Case，创建新 ID

验证 B2。

### Scenario 5：Channel 变化

先填 dependent fields，再改变 Channel。

验证：

- reducer action；
- dependent cleanup；
- UI visibility；
- stale value 不残留；
- Action Preview。

### Scenario 6：参考 Use Case 预填

验证：

- 已有值；
- confirmation-style question；
- 不重复问；
- evidence/confidence。

### Scenario 7：冲突输入

验证 conflict resolver。

### Scenario 8：跨模块高亮

验证右侧问题涉及其他模块字段时：

- 对应字段高亮；
- 模块提示；
- 不误高亮；
- 状态经过 reducer。

### Scenario 9：Content Preparation

验证独立模块和状态。

### Scenario 10：Message Templates

验证与 Content Preparation 分离。

### Scenario 11：多语言多渠道 AC

期望：

```text
AC1: Whether a Chinese SMS body is provided.
AC2: Whether an English SMS body is provided.
AC3: Whether a Chinese Email body is provided.
AC4: Whether an English Email body is provided.
```

不得出现：

- Given；
- When；
- Then；
- Pass Criteria；
- Bilingual；
- requirement_summary 依赖。

### Scenario 12：Validation Report

验证用户补充输入和报告。

### Scenario 13：Released

验证完整状态转换和 release check。

---

## 测试层级

### Unit

- Metadata；
- Dependency；
- Reducer；
- Candidate Collector；
- Ranker；
- Planner；
- Conflict；
- Validation；
- AC output。

### Contract

- API；
- React API Client；
- Error。

### Regression

- Phase 2 每个 Bug ID。

### Integration

- 前端状态到后端；
- 后端响应到 reducer；
- dependency cleanup；
- workflow。

### E2E

- 13 个业务剧本。

### Visual

- 推荐窗口尺寸至少：
  - 1366×768；
  - 1440×900；
  - 较窄桌面宽度。

---

## 输出文件

创建：

```text
recovered-main/recovery-docs/final-test-report.md
recovered-main/recovery-docs/final-capability-matrix.md
recovered-main/recovery-docs/state-mutation-audit.md
recovered-main/recovery-docs/frontend-visual-verification.md
recovered-main/recovery-docs/e2e-scenario-report.md
recovered-main/recovery-docs/final-open-risks.md
```

---

## 最终结论枚举

只能使用以下之一：

```text
READY FOR INTERNAL DEMO
READY FOR BUSINESS UAT
NOT READY — TARGETED FIXES REQUIRED
NOT READY — ARCHITECTURAL ISSUES REMAIN
```

### READY FOR INTERNAL DEMO

允许少量已记录的非阻塞问题，但核心剧本通过。

### READY FOR BUSINESS UAT

必须：

- 核心和高风险测试全部通过；
- 无未解释 direct mutation；
- API Contract 通过；
- Bug 回归测试通过；
- 13 个剧本通过；
- 视觉和交互满足业务预期。

---

## 验收标准

1. 所有测试有执行证据。
2. 所有 Bug ID 有结果。
3. 所有 Capability ID 有最终状态。
4. State mutation 有审计。
5. React 交互没有被静态 HTML 逻辑替代。
6. HTML Demo 排版目标已验证。
7. 13 个业务剧本有逐项结果。
8. 失败项不被隐藏。
9. 给出明确发布建议。
10. 第一轮验收未随意改代码。

---

## 最终回复格式

```markdown
## Phase 5 Result

- Final recommendation:
- Unit:
- Contract:
- Regression:
- Integration:
- E2E:
- Visual:
- Invalid direct mutations:
- Failed Capability IDs:
- Failed Bug IDs:
- Blocking risks:
- Reports created:
```
