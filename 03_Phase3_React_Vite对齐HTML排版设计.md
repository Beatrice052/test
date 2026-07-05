# Phase 3 — React + Vite 对齐 HTML Demo 排版设计

## 角色

你是高级前端架构师和 UI 迁移工程师。本阶段只设计“如何把 HTML Demo 的排版迁移到原 React + Vite 项目”，不得直接重写前端。

---

## 最终前端原则

### 正式前端

```text
React + Vite
```

### HTML Demo 的角色

HTML Demo 仅作为：

- 页面布局参考；
- 视觉结构参考；
- 区域排列参考；
- 间距和尺寸参考；
- 业务展示顺序参考；
- CSS 风格参考。

HTML Demo 不自动成为：

- 正式状态管理；
- 正式 API 调用层；
- 正式表单逻辑；
- 正式路由；
- 正式 reducer；
- 正式交互实现。

### 必须保留的 React 能力

优先保留：

- 组件化；
- 路由；
- 原有状态管理；
- reducer/action；
- 表单联动；
- 字段高亮；
- 跨模块高亮；
- AI 对话交互；
- validation；
- loading/error 状态；
- API Client；
- 可测试性；
- 可维护性。

---

## 必须先读取

```text
reports/phase-status.md
reports/decision-register.md
reports/phase1/frontend-symbol-index.json
reports/phase1/api-route-index.json
reports/phase2/02-api-contract-matrix.md
reports/phase2/05-source-of-truth-map.md
inputs/business-rules.md
```

然后只读取：

- React + Vite 前端短名单文件；
- HTML Demo 的 HTML/CSS/JS；
- 前端 API Client；
- State/Reducer；
- 相关测试。

不得重新分析全部后端。

---

## 强制限制

1. 不得把纯 HTML 页面整体复制进 React 后作为最终实现。
2. 不得用 `dangerouslySetInnerHTML` 承载主页面。
3. 不得删除原 React 交互逻辑，只为了快速还原视觉。
4. 不得把状态逻辑塞入 CSS 或 DOM query。
5. 不得使用大量 `document.querySelector` 代替 React state。
6. 不得让 HTML Demo 的临时 JS 覆盖 React reducer。
7. 不得开始编码。
8. 完成后必须停止。

---

## Token 节省策略

### A. 先做页面区域映射

只抽取 DOM 结构、CSS class 和 React component tree，不解释每一行代码。

### B. 使用截图或页面区域 ID

如果本地可运行，可通过页面截图或 DOM 结构确认布局。不要把完整 HTML/CSS 粘贴进报告。

### C. 只深读交互关键点

优先读取：

- App shell；
- Workflow stepper；
- Module navigation；
- Form renderer；
- Assistant/chat panel；
- Field highlight；
- Action Preview；
- API Client；
- State/Reducer。

### D. 使用差异表代替大段描述

---

## 执行步骤

### Step 1：建立 React 前端能力清单

记录：

- 路由；
- 页面；
- 组件；
- State；
- Reducer；
- Action；
- Hook；
- API Client；
- Form renderer；
- Validation；
- Highlight；
- Chat；
- Action Preview；
- Workflow。

输出：

```text
reports/phase3/01-react-capability-map.md
```

### Step 2：建立 HTML Demo 视觉结构清单

把 HTML Demo 拆成业务区域：

- 顶部 9 步流程；
- 左侧模块索引；
- 中央表单；
- 右侧统一对话/引导区；
- Question reason；
- Action Preview；
- Validation/Release 区；
- 响应式规则；
- 宽度、间距、sticky、scroll 行为。

输出：

```text
reports/phase3/02-html-layout-spec.md
```

只记录结构和视觉规则，不把 HTML JS 当成正式逻辑。

### Step 3：建立逐区域映射

输出：

```text
reports/phase3/03-layout-to-react-mapping.md
```

格式：

| Layout Area | HTML source | Existing React component | Action |
|---|---|---|---|
| Workflow header | ... | WorkflowStepper | Restyle |
| Left navigation | ... | ModuleSidebar | Recompose |
| Main form | ... | DynamicForm | Preserve logic, change layout |
| Assistant panel | ... | GuidancePanel + ChatPanel | Merge presentation only |
| Action Preview | ... | ActionPreview | Restyle |
| Field highlight | CSS reference | FieldWrapper | Preserve reducer-driven logic |

Action 只能是：

- Keep；
- Restyle；
- Recompose；
- Extract；
- Merge presentation；
- Add wrapper；
- Rewrite small isolated component。

不得写“replace entire React app with HTML”。

### Step 4：建立交互保留矩阵

输出：

```text
reports/phase3/04-interaction-preservation-matrix.md
```

至少检查：

- 表单编辑；
- 自动预填；
- 确认式问题；
- 每轮 1–3 问题；
- 模块跳转；
- 字段高亮；
- 跨模块高亮；
- Action Preview；
- validation；
- back navigation；
- loading；
- error；
- unsaved state；
- workflow transition；
- API response handling。

每项记录：

- 当前 React 实现；
- HTML Demo 表现；
- 最终保留逻辑；
- 视觉变化；
- 测试要求。

### Step 5：设计 CSS 和组件迁移策略

优先方案：

1. 保留 React component tree。
2. 增加页面级 Layout Shell。
3. 提取 HTML Demo 的颜色、间距、尺寸为 design tokens。
4. 把 HTML CSS 重写为 React 项目中的模块化 CSS。
5. 避免大范围全局选择器。
6. 避免依赖 DOM 层级的脆弱样式。
7. 保持现有 state 和 event handler。
8. 仅在必要时拆分或组合展示组件。

输出：

```text
reports/phase3/05-frontend-migration-design.md
```

### Step 6：设计前端改造批次

按以下小批次规划：

1. App shell 和全局 tokens；
2. 顶部 Workflow Stepper；
3. 左侧 Module Sidebar；
4. Main Form Layout；
5. Assistant/Chat 视觉合并；
6. Action Preview；
7. Field Highlight；
8. Responsive；
9. API Client alignment；
10. Interaction regression tests。

每批次包含：

- Change ID；
- React files；
- HTML reference files；
- 不得改变的逻辑；
- 验收截图或行为；
- Tests；
- Commit message；
- Rollback。

输出：

```text
reports/phase3/06-frontend-implementation-plan.md
```

### Step 7：建立视觉与行为验收表

输出：

```text
reports/phase3/07-frontend-acceptance-checklist.md
```

至少包含：

#### 视觉

- 9 步流程紧凑；
- 无不必要横向滚动；
- 左中右结构正确；
- 表单可纵向滚动；
- Assistant 区布局接近 HTML Demo；
- Acceptance Criteria Validation 不贴边；
- 多尺寸窗口可用。

#### 行为

- 原 React 交互不退化；
- State 不通过 DOM 直接修改；
- Highlight 仍由状态驱动；
- API 错误可见；
- Loading 正常；
- 表单值不丢失；
- Workflow 不被纯 CSS 影响。

### Step 8：更新决策登记

记录：

- React + Vite 为 canonical frontend；
- HTML Demo 为 visual specification；
- 哪些 React 组件保留；
- 哪些展示组件调整；
- 哪些 HTML JS 明确不迁移。

---

## 验收标准

Phase 3 只有同时满足以下条件才算通过：

1. 明确 React + Vite 是正式前端。
2. HTML Demo 只作为视觉参考。
3. React 组件和 HTML 区域有逐项映射。
4. 原 React 交互有保留矩阵。
5. 不存在整页 HTML 替换方案。
6. 不使用 DOM query 代替 React state。
7. 有分批实现顺序。
8. 每批次有验收标准和测试。
9. 后端没有被重新全量分析。
10. 未开始编码。

---

## 最终回复格式

```markdown
## Phase 3 Result

- Status: PASS / FAIL
- Canonical frontend:
- Visual reference:
- React interactions preserved:
- Components to restyle:
- Components to recompose:
- HTML scripts explicitly not migrated:
- Implementation batches:
- Reports created:
- Candidate source modified: YES / NO
- Blockers:
- Ready for Phase 4: YES / NO
```

完成后停止。
