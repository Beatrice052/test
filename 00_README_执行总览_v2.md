# AI-Guided Requirement Intake 多版本恢复方案 V2

## 1. 本次恢复的真实范围

HTML Demo 展示了完整的 **MDC Messaging SDLC**，但这不代表本次需要恢复整套 SDLC 系统。

本次 `recovered-main` 的正式产品范围只包括：

1. 用户输入原始 Requirement；
2. 检索和选择历史 Use Case；
3. 处理 A / B1 / B2 / C 分支；
4. AI 引导用户填写全部 Use Case 字段；
5. 完成 33 字段、4 模块的需求收集；
6. 生成 Acceptance Criteria；
7. 保留 Validation 输入与 Validation Report 能力。

以下 Demo 内容不属于本次恢复范围：

- Content Preparation 静态页面；
- Message Template Development 静态页面；
- Compliance Review 静态页面；
- UAT 静态页面；
- AC Verification 静态页面；
- Release 静态页面；
- 其他由同事添加、但没有真实后端逻辑的 MDC SDLC 展示页面。

这些页面可以保留在历史 Demo 中作为背景资料，但不得迁入 `recovered-main` 作为正式功能。

---

## 2. 最终技术决策

### 正式前端

使用原来的：

```text
React + Vite
```

原因：

- 交互完整；
- 组件化；
- 状态管理更清楚；
- 表单联动更好；
- 字段高亮更好；
- 后续维护成本更低。

### HTML Demo 的作用

HTML Demo 只作为以下内容的参考：

- 页面整体排版；
- 顶部区域布局；
- 左侧模块导航；
- 中间表单区域；
- 右侧 AI 引导区域；
- 卡片样式；
- 间距、尺寸、滚动和视觉层级。

HTML Demo 中的静态 SDLC 页面和临时 JavaScript 不作为正式功能来源。

### 正式后端

后端不按目录整体选“最新版”。

Codex 需要从全部历史后端中分别确认：

- 最稳定的后端骨架；
- 最完整的 AI 引导流程；
- 最完整的 State / Reducer；
- 最完整的 Metadata / Dependency；
- 最完整的 AC；
- 最完整的 Validation；
- 已经修复过的旧 Bug。

---

## 3. 恢复后的目标流程

```text
Step 1  Requirement Input
        ↓
Step 2  Historical Use Case Retrieval
        ↓
Step 3  Use Case Decision
        ├── A  Reuse unchanged
        ├── B1 Modify and keep original ID
        ├── B2 Modify and create new ID
        └── C  Create new Use Case
        ↓
Step 4  AI-Guided Use Case Form
        ├── 33 fields
        ├── 4 modules
        ├── dependency handling
        ├── conflict resolution
        ├── 1–3 questions per turn
        └── all required fields completed
        ↓
Step 5  Acceptance Criteria Generation
        ↓
Step 6  Validation
        ├── screenshot or text input
        └── Validation Report
```

本次恢复到 Step 6 为止。

---

## 4. Validation 的特殊处理

当前 Validation 外部 API 暂时不可用，但现有代码逻辑与原后端流程一致，代码本身需要保留。

Codex 不得因为外部 API 调用失败而：

- 删除 Validation；
- 把 Validation 标记为无效；
- 重写整套 Validation；
- 用静态页面替代真实代码；
- 把外部环境问题误判为代码回归。

正确做法：

1. 保留当前 Validation 代码；
2. 检查 Request / Response Contract；
3. 使用 mock adapter 验证本地流程；
4. 使用 contract test 验证输入输出；
5. 把 live API 测试标记为 external dependency；
6. 在 API 恢复后再执行 live integration test。

---

## 5. 五个恢复阶段

| 阶段 | 目标 | 是否改业务代码 |
|---|---|---:|
| Phase 1 | 机械盘点并识别范围 | 否 |
| Phase 2 | 比较后端能力并选基线 | 否 |
| Phase 3 | 设计 React 对齐 HTML 排版 | 否 |
| Phase 4 | 创建 recovered-main 并实施 | 是 |
| Phase 5 | 独立测试与最终验收 | 第一轮否 |

---

## 6. 工作区

```text
ai-intake-recovery/
├── candidates/
│   ├── react-original/
│   ├── version-a/
│   ├── version-b/
│   ├── version-c/
│   └── html-demo/
├── inputs/
│   ├── recovery-notes.md
│   └── business-rules.md
├── tools/
├── reports/
├── recovered-main/
└── phase-prompts/
```

---

## 7. 范围控制原则

### In Scope

- Requirement；
- Use Case retrieval；
- A/B1/B2/C；
- 33 字段；
- 4 模块；
- AI 引导；
- Dependency；
- Conflict；
- Question Planner；
- State / Reducer；
- AC；
- Validation；
- React + Vite；
- HTML Demo 的相关排版。

### Out of Scope

- 完整 MDC Messaging SDLC 的所有静态页面；
- Content Preparation；
- Message Template Development；
- UAT；
- Release；
- 同事增加但没有真实后端的展示页面；
- 与需求收集无关的大规模架构重构；
- 非必要框架升级。

---

## 8. Token 节省原则

1. Phase 1 先做文件哈希和 Symbol 索引；
2. 静态 SDLC 页面只登记，不深入分析；
3. 后续阶段只读 `deep-read-shortlist`；
4. 每个阶段单独开启 Codex 会话；
5. 报告写入文件，聊天只输出摘要；
6. 每次只处理一个 Change ID；
7. Validation 使用 mock，避免反复调用不可用 API；
8. 不做无关重构；
9. 不输出完整 diff；
10. 每阶段结束后强制停止。
