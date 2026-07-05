# AI-Guided Requirement Intake
# Final Business Rules V2

## 1. Product Scope

本项目不是完整 MDC Messaging SDLC 系统。

正式功能范围为：

```text
Requirement Input
→ Historical Use Case Retrieval
→ Use Case Decision
→ AI-Guided Use Case Form
→ Acceptance Criteria Generation
→ Validation
```

恢复版本到 Validation 为止。

---

## 2. Out-of-Scope

以下内容不属于本次恢复：

- Content Preparation；
- Message Template Development；
- Compliance Review；
- UAT；
- Release；
- Demo 中其他 MDC Messaging SDLC 静态页面；
- 同事为 Demo 制作、但没有真实后端支持的展示内容。

这些页面不得进入正式 `recovered-main`。

---

## 3. Canonical Frontend

- 正式前端使用 React + Vite。
- HTML Demo 只作为视觉和排版参考。
- 原 React 的交互、组件、状态管理、Reducer、表单联动和高亮能力应尽量保留。
- 不允许把完整 HTML 页面直接嵌入 React 作为主实现。
- 不允许用 DOM query 替代 React State。
- 不迁移 HTML Demo 中与本项目无关的静态 SDLC 页面。

---

## 4. Requirement

- 系统保留用户原始 `user_requirement`。
- 不使用过时的 `requirement_summary` 作为 AC 生成输入。
- Requirement 可以用于历史 Use Case 检索和字段预填。
- 所有自动预填应保留来源证据和置信度。

---

## 5. Historical Use Case

系统支持检索历史 Use Case。

### Option A

复用历史 Use Case，不修改。

### Option B1

修改历史 Use Case，但保留原 Use Case ID。

### Option B2

修改历史 Use Case，并生成新的 Use Case ID。

### Option C

创建全新 Use Case。

系统必须明确记录当前分支，不能混淆 B1 和 B2。

---

## 6. AI-Guided Form

### Field Model

- 总字段数：33。
- 总模块数：4。
- Metadata 中应至少包含：
  - name；
  - description；
  - example；
  - enum；
  - allow_multi；
  - default；
  - required/P0；
  - prefillable；
  - visibility。

### Guidance Rules

- 每轮提出 1–3 个问题。
- P0 必填优先。
- Dependency blocker 优先。
- Conflict 需要澄清。
- 同一组未完成字段按业务相关性继续。
- 参考 Use Case 已有字段优先使用确认式问题。
- 缺失字段使用补充式问题。
- 不重复询问已经确认的字段。
- 不询问当前不可见或无关字段。

### Dependency Rules

- 控制字段变化后，自动清理无效 dependent values。
- 支持跨模块依赖。
- 支持互斥和冲突。
- 无关字段应隐藏。
- State 清理必须通过 reducer 或统一状态转换入口。

### Question Planning

- Candidate Collector 负责候选问题池。
- Ranker 优先级：
  1. P0；
  2. Blocker；
  3. Conflict；
  4. Group completion。
- Next Question Planner 每轮最多返回 3 个问题。
- 每个问题应关联字段和提问原因。

### UI Guidance

- 左侧展示 4 个模块；
- 中间展示完整表单；
- 右侧为统一 AI 引导/对话区域；
- 显示为什么询问；
- 显示 Action Preview；
- 当前问题涉及字段应高亮；
- 支持跨模块高亮。

### Action Preview

外层只显示业务可理解变化。

### InternalImpactPlan

内部记录：

- dependency cleanup；
- hidden field changes；
- state impact；
- 后续提问影响。

---

## 7. Completion

Guided Form 完成条件：

- 所有 P0 字段完成；
- 所有当前条件必填字段完成；
- 冲突已解决；
- 依赖一致；
- 不存在阻塞状态；
- 用户可以确认 Use Case Form 完成。

---

## 8. Acceptance Criteria Generation

### Input

- 原始 `user_requirement`；
- confirmed use case；
- confirmed channels；
- required languages。

### Output

只输出 AC 文本行。

示例：

```text
AC1: Whether a Chinese SMS body is provided.
AC2: Whether an English SMS body is provided.
AC3: Whether a Chinese Email body is provided.
AC4: Whether an English Email body is provided.
```

### Prohibited Output

不得输出：

- Given；
- When；
- Then；
- Pass Criteria；
- requirement_summary；
- Bilingual。

每种语言和渠道必须分别生成 AC。

---

## 9. Validation

### Input

Validation 支持：

- screenshot；
- text；
- 其他当前实现已经支持的输入。

### Output

输出 Validation Report。

### Current API Limitation

当前 live Validation API 暂时不可用。

这属于外部环境或接口可用性问题，不应自动判定为代码错误。

### Recovery Rule

- 保留现有 Validation 代码；
- 保留与原后端一致的流程；
- 验证 Request / Response Contract；
- 提供 mock adapter；
- 提供 contract test；
- 提供 error handling test；
- live API 测试单独标记。

### Prohibited Changes

不得仅因 live API 不可用而：

- 删除 Validation；
- 用静态页面替代；
- 重写整套流程；
- 标记为废弃；
- 把外部错误误判为业务代码 Bug。

---

## 10. State Management

以下核心状态应通过 reducer 或统一状态转换入口修改：

- current requirement；
- selected use case；
- branch A/B1/B2/C；
- form fields；
- module completion；
- current questions；
- highlighted fields；
- dependency cleanup；
- conflicts；
- Action Preview；
- AC；
- Validation；
- Validation Report。

UI 组件不得直接修改核心业务状态。

---

## 11. Frontend Visual Rules

React 前端应参考 HTML Demo 的相关排版：

- 紧凑顶部区域；
- 左侧模块导航；
- 中间完整表单；
- 右侧 AI 引导；
- Action Preview；
- AC 区域；
- Validation 区域；
- 无不必要横向滚动；
- 多桌面尺寸可用。

只参考与真实范围有关的 HTML 页面。

---

## 12. Acceptance Boundary

恢复完成标准：

1. A/B1/B2/C 可用；
2. 33 字段可完成；
3. 4 模块可导航；
4. 每轮 1–3 问；
5. Dependency 正确；
6. Conflict 正确；
7. Cross-module highlight 正确；
8. State 统一；
9. AC 正确；
10. Validation 本地 mock 和 contract 正确；
11. React + Vite 保留；
12. HTML 相关排版已迁移；
13. 静态 SDLC 页面未迁移。
