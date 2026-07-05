# Phase 3 — React + Vite 对齐 HTML Demo 排版设计 V2

## 目标

使用 React + Vite 作为正式前端。

只参考 HTML Demo 中与以下功能有关的页面布局：

- Requirement；
- Use Case selection；
- AI Guided Form；
- AC；
- Validation。

Demo 中其他 MDC Messaging SDLC 静态页面不迁移。

---

## 强制原则

1. React + Vite 是 canonical frontend；
2. HTML 是 visual reference；
3. 保留 React state、reducer、hooks、components；
4. 不使用整页 HTML 嵌入；
5. 不使用 `dangerouslySetInnerHTML` 承载主页面；
6. 不使用 DOM query 代替 React State；
7. 不迁移静态 SDLC 页面；
8. 本阶段不编码。

---

## 需要分析的 React 能力

- Requirement page；
- Use Case retrieval；
- Use Case branch selection；
- Module sidebar；
- Dynamic form；
- AI chat/guidance；
- Question reason；
- Field highlight；
- Cross-module highlight；
- Action Preview；
- AC page；
- Validation page；
- API client；
- State / Reducer；
- Loading/Error。

---

## 需要参考的 HTML 内容

- 页面整体 grid；
- 顶部 header；
- 左中右布局；
- 表单区域；
- 右侧 AI 区；
- 卡片；
- spacing；
- width；
- sticky；
- scroll；
- responsive；
- AC 与 Validation 的视觉。

不参考：

- Content Preparation 页面逻辑；
- Template 页面逻辑；
- UAT 页面逻辑；
- Release 页面逻辑；
- 同事制作的静态 JS。

---

## 输出

```text
reports/phase3/01-react-capability-map.md
reports/phase3/02-html-layout-spec.md
reports/phase3/03-layout-to-react-mapping.md
reports/phase3/04-interaction-preservation-matrix.md
reports/phase3/05-frontend-migration-design.md
reports/phase3/06-frontend-implementation-plan.md
reports/phase3/07-frontend-acceptance-checklist.md
```

### 页面映射格式

| In-scope area | HTML reference | React component | Action | Logic preserved |
|---|---|---|---|---|

### Action 仅允许

- Keep；
- Restyle；
- Recompose；
- Extract；
- Add wrapper；
- Small isolated rewrite。

---

## 视觉验收

- 顶部区域紧凑；
- 无不必要横向滚动；
- 左侧模块清楚；
- 中间表单完整；
- 右侧 AI 引导清楚；
- AC 区不贴边；
- Validation 区清楚；
- 多窗口尺寸可用。

## 行为验收

- 表单值不丢；
- React state 不退化；
- Highlight 状态驱动；
- 一轮 1–3 问；
- 模块跳转正常；
- Action Preview 正常；
- AC 正常；
- Validation mock 流程正常；
- Error/Loading 正常。

---

## 验收标准

1. React 是正式前端；
2. HTML 仅为视觉参考；
3. 只覆盖真实范围；
4. 静态 SDLC 页面明确排除；
5. 原 React 交互有保留矩阵；
6. 没有整页替换；
7. 没有 DOM 驱动业务状态；
8. 有批次和测试；
9. 未编码；
10. 未改 candidates。

---

## 最终回复

```markdown
## Phase 3 Result

- Status:
- Canonical frontend:
- Visual reference scope:
- Out-of-scope SDLC pages excluded:
- Components to restyle:
- Components to recompose:
- Interactions preserved:
- Implementation batches:
- Candidate source modified:
- Blockers:
- Ready for Phase 4:
```
