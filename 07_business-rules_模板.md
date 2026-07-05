# Final Business Rules

本文件只写最终必须满足的业务规则，不写版本猜测。

## 1. Canonical frontend

- 正式前端必须使用 React + Vite。
- HTML Demo 仅作为视觉和排版参考。
- 原 React 的交互能力应尽量保留。
- 不允许用静态 HTML 脚本替换 React 状态和交互。

## 2. Workflow

- 总流程为 9 个步骤。
- 请在下方补充最终步骤名称和允许跳转：

| Step | Name | Active in current scope | Transition rule |
|---:|---|---|---|
| 1 |  |  |  |
| 2 | Content Preparation |  |  |
| 3 |  |  |  |
| 4 |  |  |  |
| 5 |  |  |  |
| 6 | Ready for Template Development |  |  |
| 7 |  |  |  |
| 8 |  |  |  |
| 9 | Released |  |  |

## 3. Use Case branches

- A：原样复用历史 Use Case。
- B1：修改历史 Use Case，但 ID 不变。
- B2：修改历史 Use Case，并创建新 ID。
- C：创建全新 Use Case。

## 4. AI-guided intake

- 字段数：33。
- 模块数：4。
- 每轮问题数：1–3。
- P0 优先。
- Blocker 优先。
- Conflict 需要澄清。
- 参考 Use Case 已有值应优先使用确认式问题。
- 控制字段变化后，应清理无效依赖字段。
- 支持跨模块字段高亮。
- Action Preview 展示业务可理解变更。
- InternalImpactPlan 用于内部状态和审计。

## 5. Content and Template

- Content Preparation 与 Message Templates 是两个独立模块。
- Content 完成后按当前业务流程进入 Template Development。
- 请补充其他最终规则：

## 6. Acceptance Criteria

- 输入使用原始 `user_requirement`。
- 不使用 `requirement_summary`。
- 依据 confirmed channels 和 language list。
- 仅输出 AC 文本行。
- 不输出 Given/When/Then/Pass Criteria。
- 不使用 `Bilingual`。
- 每个语言和渠道分别生成。

示例：

```text
AC1: Whether a Chinese SMS body is provided.
AC2: Whether an English SMS body is provided.
```

## 7. Validation and Release

- Validation 支持用户补充截图或文本。
- 输出 Validation Report。
- Release 前应执行最终检查。
- 请补充最终检查项：

## 8. UI acceptance

- 顶部流程紧凑。
- 不出现不必要的横向滚动。
- 左侧模块索引。
- 中间完整表单。
- 右侧统一 AI 引导/对话区。
- 展示为何提问。
- 展示 Action Preview。
- Acceptance Criteria Validation 不贴边。
- 跨模块高亮正确。
